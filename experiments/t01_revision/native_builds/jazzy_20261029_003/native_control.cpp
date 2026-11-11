// A lockstep MuJoCo adapter using the real ros2_control ControllerManager.
// Existing standing/PD reference generation is retained; every actuator command
// must pass through the managed controller and hardware interface before mj_step.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <future>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#include "controller_manager/controller_manager.hpp"
#include "controller_interface/controller_interface.hpp"
#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/types/hardware_interface_type_values.hpp"
#include "lifecycle_msgs/msg/state.hpp"
#include "pluginlib/class_list_macros.hpp"
#include "rclcpp/rclcpp.hpp"

namespace thesis_kernel {
using CallbackReturn = rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn;
std::vector<std::string> joints;
std::vector<double> positions, velocities, references, commands, written;
std::string error;
uint64_t updates = 0, writes = 0, cycles = 0;
int64_t period_ns = 2000000;
std::shared_ptr<rclcpp::executors::SingleThreadedExecutor> executor;
std::shared_ptr<controller_manager::ControllerManager> manager;
controller_interface::ControllerInterfaceBaseSharedPtr controller;
controller_interface::ControllerInterfaceBaseSharedPtr competitor;

class MujocoSystem : public hardware_interface::SystemInterface {
public:
  CallbackReturn on_init(const hardware_interface::HardwareInfo & info) override {
    if (hardware_interface::SystemInterface::on_init(info) != CallbackReturn::SUCCESS)
      return CallbackReturn::ERROR;
    return info.joints.size() == joints.size() ? CallbackReturn::SUCCESS : CallbackReturn::ERROR;
  }
  std::vector<hardware_interface::StateInterface> export_state_interfaces() override {
    std::vector<hardware_interface::StateInterface> result;
    for (size_t i = 0; i < joints.size(); ++i) {
      result.emplace_back(joints[i], "position", &positions[i]);
      result.emplace_back(joints[i], "velocity", &velocities[i]);
    }
    return result;
  }
  std::vector<hardware_interface::CommandInterface> export_command_interfaces() override {
    std::vector<hardware_interface::CommandInterface> result;
    for (size_t i = 0; i < joints.size(); ++i)
      result.emplace_back(joints[i], "position", &commands[i]);
    return result;
  }
  hardware_interface::return_type read(const rclcpp::Time &, const rclcpp::Duration &) override {
    return hardware_interface::return_type::OK;
  }
  hardware_interface::return_type write(const rclcpp::Time &, const rclcpp::Duration &) override {
    written = commands;
    ++writes;
    return hardware_interface::return_type::OK;
  }
};

class ReferenceController : public controller_interface::ControllerInterface {
public:
  CallbackReturn on_init() override { return CallbackReturn::SUCCESS; }
  controller_interface::InterfaceConfiguration command_interface_configuration() const override {
    controller_interface::InterfaceConfiguration result;
    result.type = controller_interface::interface_configuration_type::INDIVIDUAL;
    for (const auto & name : joints) result.names.push_back(name + "/position");
    return result;
  }
  controller_interface::InterfaceConfiguration state_interface_configuration() const override {
    return {controller_interface::interface_configuration_type::NONE, {}};
  }
  controller_interface::return_type update(const rclcpp::Time &, const rclcpp::Duration &) override {
    if (command_interfaces_.size() != references.size())
      return controller_interface::return_type::ERROR;
    for (size_t i = 0; i < references.size(); ++i) {
      if (!std::isfinite(references[i])) return controller_interface::return_type::ERROR;
      if (!command_interfaces_[i].set_value(references[i]))
        return controller_interface::return_type::ERROR;
    }
    ++updates;
    return controller_interface::return_type::OK;
  }
};

void cycle() {
  const rclcpp::Time time(++cycles * period_ns, RCL_STEADY_TIME);
  const auto period = rclcpp::Duration::from_nanoseconds(period_ns);
  manager->read(time, period);
  if (manager->update(time, period) != controller_interface::return_type::OK)
    throw std::runtime_error("ControllerManager update failed");
  manager->write(time, period);
}

controller_interface::return_type switch_to(const std::vector<std::string> & activate,
                                            const std::vector<std::string> & deactivate) {
  auto future = std::async(std::launch::async, [&]() {
    return manager->switch_controller(activate, deactivate, 2, false,
                                     rclcpp::Duration::from_seconds(5.));
  });
  for (int attempt = 0; attempt < 6000; ++attempt) {
    if (future.wait_for(std::chrono::milliseconds(0)) == std::future_status::ready)
      return future.get();
    cycle();
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }
  throw std::runtime_error("Controller switch timed out");
}

std::string description() {
  std::ostringstream xml;
  xml << "<robot name='thesis_g1'><link name='base'/>";
  for (size_t i = 0; i < joints.size(); ++i)
    xml << "<link name='link" << i << "'/><joint name='" << joints[i]
        << "' type='continuous'><parent link='base'/><child link='link" << i
        << "'/><axis xyz='0 0 1'/><limit effort='1000' velocity='100'/></joint>";
  xml << "<ros2_control name='MujocoAdapter' type='system'><hardware>"
      << "<plugin>thesis_kernel/MujocoSystem</plugin></hardware>";
  for (const auto & name : joints)
    xml << "<joint name='" << name << "'><command_interface name='position'/>"
        << "<state_interface name='position'/><state_interface name='velocity'/></joint>";
  xml << "</ros2_control></robot>";
  return xml.str();
}
}  // namespace thesis_kernel

PLUGINLIB_EXPORT_CLASS(thesis_kernel::MujocoSystem, hardware_interface::SystemInterface)
PLUGINLIB_EXPORT_CLASS(thesis_kernel::ReferenceController, controller_interface::ControllerInterface)

extern "C" {
const char * thesis_error() { return thesis_kernel::error.c_str(); }
int thesis_create(const char * names, double timestep) {
  using namespace thesis_kernel;
  try {
    if (manager) throw std::runtime_error("Only one live physical control owner is allowed");
    joints.clear();
    std::istringstream input(names);
    std::string name;
    while (std::getline(input, name, '\n')) {
      if (name.empty() || name.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_") != std::string::npos)
        throw std::runtime_error("Invalid joint name");
      joints.push_back(name);
    }
    if (joints.empty() || !std::isfinite(timestep) || timestep <= 0.)
      throw std::runtime_error("Invalid joint set or timestep");
    positions.assign(joints.size(), 0.); velocities = positions;
    references = positions; commands = positions; written = positions;
    updates = writes = cycles = 0;
    period_ns = std::llround(timestep * 1e9);
    if (!rclcpp::ok()) rclcpp::init(0, nullptr);
    executor = std::make_shared<rclcpp::executors::SingleThreadedExecutor>();
    auto options = controller_manager::get_cm_node_options();
    options.parameter_overrides({rclcpp::Parameter("update_rate", static_cast<int>(std::llround(1. / timestep))),
                                 rclcpp::Parameter("enforce_command_limits", false)});
    manager = std::make_shared<controller_manager::ControllerManager>(
        executor, description(), true, "controller_manager", "/thesis_t01", options);
    executor->add_node(manager);
    controller = manager->load_controller("mujoco_references", "thesis_kernel/ReferenceController");
    if (!controller || manager->configure_controller("mujoco_references") != controller_interface::return_type::OK)
      throw std::runtime_error("Cannot configure reference controller");
    // Prepare the inactive competitor before starting the externally stepped loop.
    // Loading another controller later requires a concurrently ticking RT loop.
    competitor = manager->load_controller("competing_references", "thesis_kernel/ReferenceController");
    if (!competitor || manager->configure_controller("competing_references") != controller_interface::return_type::OK)
      throw std::runtime_error("Cannot configure competing controller for resource test");
    if (switch_to({"mujoco_references"}, {}) != controller_interface::return_type::OK)
      throw std::runtime_error("Cannot activate reference controller");
    return 0;
  } catch (const std::exception & exception) { error = exception.what(); return 1; }
}
int thesis_step(const double * q, const double * dq, const double * desired, double * accepted, int count) {
  using namespace thesis_kernel;
  try {
    if (!manager || count != static_cast<int>(joints.size()) ||
        controller->get_lifecycle_state().id() != lifecycle_msgs::msg::State::PRIMARY_STATE_ACTIVE)
      throw std::runtime_error("Controller inactive or state dimension mismatch");
    for (int i = 0; i < count; ++i) {
      if (!std::isfinite(q[i]) || !std::isfinite(dq[i]) || !std::isfinite(desired[i]))
        throw std::runtime_error("Non-finite input rejected before physics");
      positions[i] = q[i]; velocities[i] = dq[i]; references[i] = desired[i];
    }
    const auto old_updates = updates, old_writes = writes;
    cycle();
    if (updates != old_updates + 1 || writes != old_writes + 1)
      throw std::runtime_error("Read/update/write did not execute exactly once");
    for (int i = 0; i < count; ++i) {
      if (written[i] != desired[i]) throw std::runtime_error("Actuator reference changed in adapter");
      accepted[i] = written[i];
    }
    return 0;
  } catch (const std::exception & exception) { error = exception.what(); return 1; }
}
int thesis_conflict_probe() {
  using namespace thesis_kernel;
  try {
    const auto result = switch_to({"competing_references"}, {});
    if (result != controller_interface::return_type::ERROR ||
        controller->get_lifecycle_state().id() != lifecycle_msgs::msg::State::PRIMARY_STATE_ACTIVE ||
        competitor->get_lifecycle_state().id() == lifecycle_msgs::msg::State::PRIMARY_STATE_ACTIVE)
      throw std::runtime_error("Command interface conflict was not rejected");
    return 0;
  } catch (const std::exception & exception) { error = exception.what(); return 1; }
}
uint64_t thesis_updates() { return thesis_kernel::updates; }
uint64_t thesis_writes() { return thesis_kernel::writes; }
void thesis_destroy() {
  using namespace thesis_kernel;
  competitor.reset(); controller.reset(); manager.reset(); executor.reset();
  if (rclcpp::ok()) rclcpp::shutdown();
}
}
