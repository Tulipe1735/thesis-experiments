// generated from rosidl_typesupport_fastrtps_c/resource/idl__type_support_c.cpp.em
// with input from thesis_skill_interfaces:action/ExecuteSkill.idl
// generated code does not contain a copyright notice
#include "thesis_skill_interfaces/action/detail/execute_skill__rosidl_typesupport_fastrtps_c.h"


#include <cassert>
#include <cstddef>
#include <limits>
#include <string>
#include "rosidl_typesupport_fastrtps_c/identifier.h"
#include "rosidl_typesupport_fastrtps_c/serialization_helpers.hpp"
#include "rosidl_typesupport_fastrtps_c/wstring_conversion.hpp"
#include "rosidl_typesupport_fastrtps_cpp/message_type_support.h"
#include "thesis_skill_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
#include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
#include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
#include "fastcdr/Cdr.h"

#ifndef _WIN32
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wunused-parameter"
# ifdef __clang__
#  pragma clang diagnostic ignored "-Wdeprecated-register"
#  pragma clang diagnostic ignored "-Wreturn-type-c-linkage"
# endif
#endif
#ifndef _WIN32
# pragma GCC diagnostic pop
#endif

// includes and forward declarations of message dependencies and their conversion functions

#if defined(__cplusplus)
extern "C"
{
#endif

#include "rosidl_runtime_c/string.h"  // parameters_json, request_id, skill_id, skill_version
#include "rosidl_runtime_c/string_functions.h"  // parameters_json, request_id, skill_id, skill_version

// forward declare type support functions


using _ExecuteSkill_Goal__ros_msg_type = thesis_skill_interfaces__action__ExecuteSkill_Goal;


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_Goal(
  const thesis_skill_interfaces__action__ExecuteSkill_Goal * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: skill_id
  {
    const rosidl_runtime_c__String * str = &ros_message->skill_id;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: skill_version
  {
    const rosidl_runtime_c__String * str = &ros_message->skill_version;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: request_id
  {
    const rosidl_runtime_c__String * str = &ros_message->request_id;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: parameters_json
  {
    const rosidl_runtime_c__String * str = &ros_message->parameters_json;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_Goal(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_Goal * ros_message)
{
  // Field name: skill_id
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->skill_id.data) {
      rosidl_runtime_c__String__init(&ros_message->skill_id);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->skill_id,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'skill_id'\n");
      return false;
    }
  }

  // Field name: skill_version
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->skill_version.data) {
      rosidl_runtime_c__String__init(&ros_message->skill_version);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->skill_version,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'skill_version'\n");
      return false;
    }
  }

  // Field name: request_id
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->request_id.data) {
      rosidl_runtime_c__String__init(&ros_message->request_id);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->request_id,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'request_id'\n");
      return false;
    }
  }

  // Field name: parameters_json
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->parameters_json.data) {
      rosidl_runtime_c__String__init(&ros_message->parameters_json);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->parameters_json,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'parameters_json'\n");
      return false;
    }
  }

  return true;
}  // NOLINT(readability/fn_size)


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Goal(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_Goal__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_Goal__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: skill_id
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->skill_id.size + 1);

  // Field name: skill_version
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->skill_version.size + 1);

  // Field name: request_id
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->request_id.size + 1);

  // Field name: parameters_json
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->parameters_json.size + 1);

  return current_alignment - initial_alignment;
}


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Goal(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;

  // Field name: skill_id
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Field name: skill_version
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Field name: request_id
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Field name: parameters_json
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }


  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_Goal;
    is_plain =
      (
      offsetof(DataType, parameters_json) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_Goal(
  const thesis_skill_interfaces__action__ExecuteSkill_Goal * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: skill_id
  {
    const rosidl_runtime_c__String * str = &ros_message->skill_id;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: skill_version
  {
    const rosidl_runtime_c__String * str = &ros_message->skill_version;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: request_id
  {
    const rosidl_runtime_c__String * str = &ros_message->request_id;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: parameters_json
  {
    const rosidl_runtime_c__String * str = &ros_message->parameters_json;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Goal(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_Goal__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_Goal__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;

  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: skill_id
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->skill_id.size + 1);

  // Field name: skill_version
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->skill_version.size + 1);

  // Field name: request_id
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->request_id.size + 1);

  // Field name: parameters_json
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->parameters_json.size + 1);

  return current_alignment - initial_alignment;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Goal(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;
  // Field name: skill_id
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Field name: skill_version
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Field name: request_id
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Field name: parameters_json
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_Goal;
    is_plain =
      (
      offsetof(DataType, parameters_json) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}


static bool _ExecuteSkill_Goal__cdr_serialize(
  const void * untyped_ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  const thesis_skill_interfaces__action__ExecuteSkill_Goal * ros_message = static_cast<const thesis_skill_interfaces__action__ExecuteSkill_Goal *>(untyped_ros_message);
  (void)ros_message;
  return cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_Goal(ros_message, cdr);
}

static bool _ExecuteSkill_Goal__cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  void * untyped_ros_message)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  thesis_skill_interfaces__action__ExecuteSkill_Goal * ros_message = static_cast<thesis_skill_interfaces__action__ExecuteSkill_Goal *>(untyped_ros_message);
  (void)ros_message;
  return cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_Goal(cdr, ros_message);
}

static uint32_t _ExecuteSkill_Goal__get_serialized_size(const void * untyped_ros_message)
{
  return static_cast<uint32_t>(
    get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Goal(
      untyped_ros_message, 0));
}

static size_t _ExecuteSkill_Goal__max_serialized_size(char & bounds_info)
{
  bool full_bounded;
  bool is_plain;
  size_t ret_val;

  ret_val = max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Goal(
    full_bounded, is_plain, 0);

  bounds_info =
    is_plain ? ROSIDL_TYPESUPPORT_FASTRTPS_PLAIN_TYPE :
    full_bounded ? ROSIDL_TYPESUPPORT_FASTRTPS_BOUNDED_TYPE : ROSIDL_TYPESUPPORT_FASTRTPS_UNBOUNDED_TYPE;
  return ret_val;
}


static message_type_support_callbacks_t __callbacks_ExecuteSkill_Goal = {
  "thesis_skill_interfaces::action",
  "ExecuteSkill_Goal",
  _ExecuteSkill_Goal__cdr_serialize,
  _ExecuteSkill_Goal__cdr_deserialize,
  _ExecuteSkill_Goal__get_serialized_size,
  _ExecuteSkill_Goal__max_serialized_size,
  nullptr
};

static rosidl_message_type_support_t _ExecuteSkill_Goal__type_support = {
  rosidl_typesupport_fastrtps_c__identifier,
  &__callbacks_ExecuteSkill_Goal,
  get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_Goal__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_Goal__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_Goal__get_type_description_sources,
};

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_Goal)() {
  return &_ExecuteSkill_Goal__type_support;
}

#if defined(__cplusplus)
}
#endif

// already included above
// #include <cassert>
// already included above
// #include <cstddef>
// already included above
// #include <limits>
// already included above
// #include <string>
// already included above
// #include "rosidl_typesupport_fastrtps_c/identifier.h"
// already included above
// #include "rosidl_typesupport_fastrtps_c/serialization_helpers.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_c/wstring_conversion.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_cpp/message_type_support.h"
// already included above
// #include "thesis_skill_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "fastcdr/Cdr.h"

#ifndef _WIN32
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wunused-parameter"
# ifdef __clang__
#  pragma clang diagnostic ignored "-Wdeprecated-register"
#  pragma clang diagnostic ignored "-Wreturn-type-c-linkage"
# endif
#endif
#ifndef _WIN32
# pragma GCC diagnostic pop
#endif

// includes and forward declarations of message dependencies and their conversion functions

#if defined(__cplusplus)
extern "C"
{
#endif

// already included above
// #include "rosidl_runtime_c/string.h"  // evidence_id, execution_status, reason, runtime_check
// already included above
// #include "rosidl_runtime_c/string_functions.h"  // evidence_id, execution_status, reason, runtime_check

// forward declare type support functions


using _ExecuteSkill_Result__ros_msg_type = thesis_skill_interfaces__action__ExecuteSkill_Result;


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_Result(
  const thesis_skill_interfaces__action__ExecuteSkill_Result * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: execution_status
  {
    const rosidl_runtime_c__String * str = &ros_message->execution_status;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: runtime_check
  {
    const rosidl_runtime_c__String * str = &ros_message->runtime_check;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: reason
  {
    const rosidl_runtime_c__String * str = &ros_message->reason;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: evidence_id
  {
    const rosidl_runtime_c__String * str = &ros_message->evidence_id;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_Result(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_Result * ros_message)
{
  // Field name: execution_status
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->execution_status.data) {
      rosidl_runtime_c__String__init(&ros_message->execution_status);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->execution_status,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'execution_status'\n");
      return false;
    }
  }

  // Field name: runtime_check
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->runtime_check.data) {
      rosidl_runtime_c__String__init(&ros_message->runtime_check);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->runtime_check,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'runtime_check'\n");
      return false;
    }
  }

  // Field name: reason
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->reason.data) {
      rosidl_runtime_c__String__init(&ros_message->reason);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->reason,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'reason'\n");
      return false;
    }
  }

  // Field name: evidence_id
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->evidence_id.data) {
      rosidl_runtime_c__String__init(&ros_message->evidence_id);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->evidence_id,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'evidence_id'\n");
      return false;
    }
  }

  return true;
}  // NOLINT(readability/fn_size)


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Result(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_Result__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_Result__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: execution_status
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->execution_status.size + 1);

  // Field name: runtime_check
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->runtime_check.size + 1);

  // Field name: reason
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->reason.size + 1);

  // Field name: evidence_id
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->evidence_id.size + 1);

  return current_alignment - initial_alignment;
}


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Result(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;

  // Field name: execution_status
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Field name: runtime_check
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Field name: reason
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Field name: evidence_id
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }


  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_Result;
    is_plain =
      (
      offsetof(DataType, evidence_id) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_Result(
  const thesis_skill_interfaces__action__ExecuteSkill_Result * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: execution_status
  {
    const rosidl_runtime_c__String * str = &ros_message->execution_status;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: runtime_check
  {
    const rosidl_runtime_c__String * str = &ros_message->runtime_check;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: reason
  {
    const rosidl_runtime_c__String * str = &ros_message->reason;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: evidence_id
  {
    const rosidl_runtime_c__String * str = &ros_message->evidence_id;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Result(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_Result__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_Result__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;

  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: execution_status
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->execution_status.size + 1);

  // Field name: runtime_check
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->runtime_check.size + 1);

  // Field name: reason
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->reason.size + 1);

  // Field name: evidence_id
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->evidence_id.size + 1);

  return current_alignment - initial_alignment;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Result(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;
  // Field name: execution_status
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Field name: runtime_check
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Field name: reason
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Field name: evidence_id
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_Result;
    is_plain =
      (
      offsetof(DataType, evidence_id) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}


static bool _ExecuteSkill_Result__cdr_serialize(
  const void * untyped_ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  const thesis_skill_interfaces__action__ExecuteSkill_Result * ros_message = static_cast<const thesis_skill_interfaces__action__ExecuteSkill_Result *>(untyped_ros_message);
  (void)ros_message;
  return cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_Result(ros_message, cdr);
}

static bool _ExecuteSkill_Result__cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  void * untyped_ros_message)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  thesis_skill_interfaces__action__ExecuteSkill_Result * ros_message = static_cast<thesis_skill_interfaces__action__ExecuteSkill_Result *>(untyped_ros_message);
  (void)ros_message;
  return cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_Result(cdr, ros_message);
}

static uint32_t _ExecuteSkill_Result__get_serialized_size(const void * untyped_ros_message)
{
  return static_cast<uint32_t>(
    get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Result(
      untyped_ros_message, 0));
}

static size_t _ExecuteSkill_Result__max_serialized_size(char & bounds_info)
{
  bool full_bounded;
  bool is_plain;
  size_t ret_val;

  ret_val = max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Result(
    full_bounded, is_plain, 0);

  bounds_info =
    is_plain ? ROSIDL_TYPESUPPORT_FASTRTPS_PLAIN_TYPE :
    full_bounded ? ROSIDL_TYPESUPPORT_FASTRTPS_BOUNDED_TYPE : ROSIDL_TYPESUPPORT_FASTRTPS_UNBOUNDED_TYPE;
  return ret_val;
}


static message_type_support_callbacks_t __callbacks_ExecuteSkill_Result = {
  "thesis_skill_interfaces::action",
  "ExecuteSkill_Result",
  _ExecuteSkill_Result__cdr_serialize,
  _ExecuteSkill_Result__cdr_deserialize,
  _ExecuteSkill_Result__get_serialized_size,
  _ExecuteSkill_Result__max_serialized_size,
  nullptr
};

static rosidl_message_type_support_t _ExecuteSkill_Result__type_support = {
  rosidl_typesupport_fastrtps_c__identifier,
  &__callbacks_ExecuteSkill_Result,
  get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_Result__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_Result__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_Result__get_type_description_sources,
};

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_Result)() {
  return &_ExecuteSkill_Result__type_support;
}

#if defined(__cplusplus)
}
#endif

// already included above
// #include <cassert>
// already included above
// #include <cstddef>
// already included above
// #include <limits>
// already included above
// #include <string>
// already included above
// #include "rosidl_typesupport_fastrtps_c/identifier.h"
// already included above
// #include "rosidl_typesupport_fastrtps_c/serialization_helpers.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_c/wstring_conversion.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_cpp/message_type_support.h"
// already included above
// #include "thesis_skill_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "fastcdr/Cdr.h"

#ifndef _WIN32
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wunused-parameter"
# ifdef __clang__
#  pragma clang diagnostic ignored "-Wdeprecated-register"
#  pragma clang diagnostic ignored "-Wreturn-type-c-linkage"
# endif
#endif
#ifndef _WIN32
# pragma GCC diagnostic pop
#endif

// includes and forward declarations of message dependencies and their conversion functions

#if defined(__cplusplus)
extern "C"
{
#endif

// already included above
// #include "rosidl_runtime_c/string.h"  // event, stage
// already included above
// #include "rosidl_runtime_c/string_functions.h"  // event, stage

// forward declare type support functions


using _ExecuteSkill_Feedback__ros_msg_type = thesis_skill_interfaces__action__ExecuteSkill_Feedback;


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
  const thesis_skill_interfaces__action__ExecuteSkill_Feedback * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: stage
  {
    const rosidl_runtime_c__String * str = &ros_message->stage;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: event
  {
    const rosidl_runtime_c__String * str = &ros_message->event;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: simulation_seconds
  {
    cdr << ros_message->simulation_seconds;
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_Feedback * ros_message)
{
  // Field name: stage
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->stage.data) {
      rosidl_runtime_c__String__init(&ros_message->stage);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->stage,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'stage'\n");
      return false;
    }
  }

  // Field name: event
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->event.data) {
      rosidl_runtime_c__String__init(&ros_message->event);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->event,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'event'\n");
      return false;
    }
  }

  // Field name: simulation_seconds
  {
    cdr >> ros_message->simulation_seconds;
  }

  return true;
}  // NOLINT(readability/fn_size)


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_Feedback__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_Feedback__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: stage
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->stage.size + 1);

  // Field name: event
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->event.size + 1);

  // Field name: simulation_seconds
  {
    size_t item_size = sizeof(ros_message->simulation_seconds);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  return current_alignment - initial_alignment;
}


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;

  // Field name: stage
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Field name: event
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Field name: simulation_seconds
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }


  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_Feedback;
    is_plain =
      (
      offsetof(DataType, simulation_seconds) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
  const thesis_skill_interfaces__action__ExecuteSkill_Feedback * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: stage
  {
    const rosidl_runtime_c__String * str = &ros_message->stage;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: event
  {
    const rosidl_runtime_c__String * str = &ros_message->event;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: simulation_seconds
  {
    cdr << ros_message->simulation_seconds;
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_Feedback__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_Feedback__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;

  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: stage
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->stage.size + 1);

  // Field name: event
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->event.size + 1);

  // Field name: simulation_seconds
  {
    size_t item_size = sizeof(ros_message->simulation_seconds);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  return current_alignment - initial_alignment;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;
  // Field name: stage
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Field name: event
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Field name: simulation_seconds
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_Feedback;
    is_plain =
      (
      offsetof(DataType, simulation_seconds) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}


static bool _ExecuteSkill_Feedback__cdr_serialize(
  const void * untyped_ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  const thesis_skill_interfaces__action__ExecuteSkill_Feedback * ros_message = static_cast<const thesis_skill_interfaces__action__ExecuteSkill_Feedback *>(untyped_ros_message);
  (void)ros_message;
  return cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_Feedback(ros_message, cdr);
}

static bool _ExecuteSkill_Feedback__cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  void * untyped_ros_message)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  thesis_skill_interfaces__action__ExecuteSkill_Feedback * ros_message = static_cast<thesis_skill_interfaces__action__ExecuteSkill_Feedback *>(untyped_ros_message);
  (void)ros_message;
  return cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_Feedback(cdr, ros_message);
}

static uint32_t _ExecuteSkill_Feedback__get_serialized_size(const void * untyped_ros_message)
{
  return static_cast<uint32_t>(
    get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
      untyped_ros_message, 0));
}

static size_t _ExecuteSkill_Feedback__max_serialized_size(char & bounds_info)
{
  bool full_bounded;
  bool is_plain;
  size_t ret_val;

  ret_val = max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
    full_bounded, is_plain, 0);

  bounds_info =
    is_plain ? ROSIDL_TYPESUPPORT_FASTRTPS_PLAIN_TYPE :
    full_bounded ? ROSIDL_TYPESUPPORT_FASTRTPS_BOUNDED_TYPE : ROSIDL_TYPESUPPORT_FASTRTPS_UNBOUNDED_TYPE;
  return ret_val;
}


static message_type_support_callbacks_t __callbacks_ExecuteSkill_Feedback = {
  "thesis_skill_interfaces::action",
  "ExecuteSkill_Feedback",
  _ExecuteSkill_Feedback__cdr_serialize,
  _ExecuteSkill_Feedback__cdr_deserialize,
  _ExecuteSkill_Feedback__get_serialized_size,
  _ExecuteSkill_Feedback__max_serialized_size,
  nullptr
};

static rosidl_message_type_support_t _ExecuteSkill_Feedback__type_support = {
  rosidl_typesupport_fastrtps_c__identifier,
  &__callbacks_ExecuteSkill_Feedback,
  get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_Feedback__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_Feedback__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_Feedback__get_type_description_sources,
};

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_Feedback)() {
  return &_ExecuteSkill_Feedback__type_support;
}

#if defined(__cplusplus)
}
#endif

// already included above
// #include <cassert>
// already included above
// #include <cstddef>
// already included above
// #include <limits>
// already included above
// #include <string>
// already included above
// #include "rosidl_typesupport_fastrtps_c/identifier.h"
// already included above
// #include "rosidl_typesupport_fastrtps_c/serialization_helpers.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_c/wstring_conversion.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_cpp/message_type_support.h"
// already included above
// #include "thesis_skill_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "fastcdr/Cdr.h"

#ifndef _WIN32
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wunused-parameter"
# ifdef __clang__
#  pragma clang diagnostic ignored "-Wdeprecated-register"
#  pragma clang diagnostic ignored "-Wreturn-type-c-linkage"
# endif
#endif
#ifndef _WIN32
# pragma GCC diagnostic pop
#endif

// includes and forward declarations of message dependencies and their conversion functions

#if defined(__cplusplus)
extern "C"
{
#endif

// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"  // goal
#include "unique_identifier_msgs/msg/detail/uuid__functions.h"  // goal_id

// forward declare type support functions

bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_Goal(
  const thesis_skill_interfaces__action__ExecuteSkill_Goal * ros_message,
  eprosima::fastcdr::Cdr & cdr);

bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_Goal(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_Goal * ros_message);

size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Goal(
  const void * untyped_ros_message,
  size_t current_alignment);

size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Goal(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_Goal(
  const thesis_skill_interfaces__action__ExecuteSkill_Goal * ros_message,
  eprosima::fastcdr::Cdr & cdr);

size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Goal(
  const void * untyped_ros_message,
  size_t current_alignment);

size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Goal(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

const rosidl_message_type_support_t *
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_Goal)();

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_serialize_unique_identifier_msgs__msg__UUID(
  const unique_identifier_msgs__msg__UUID * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_deserialize_unique_identifier_msgs__msg__UUID(
  eprosima::fastcdr::Cdr & cdr,
  unique_identifier_msgs__msg__UUID * ros_message);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t get_serialized_size_unique_identifier_msgs__msg__UUID(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t max_serialized_size_unique_identifier_msgs__msg__UUID(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_serialize_key_unique_identifier_msgs__msg__UUID(
  const unique_identifier_msgs__msg__UUID * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t get_serialized_size_key_unique_identifier_msgs__msg__UUID(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t max_serialized_size_key_unique_identifier_msgs__msg__UUID(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
const rosidl_message_type_support_t *
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, unique_identifier_msgs, msg, UUID)();


using _ExecuteSkill_SendGoal_Request__ros_msg_type = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request;


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: goal_id
  {
    cdr_serialize_unique_identifier_msgs__msg__UUID(
      &ros_message->goal_id, cdr);
  }

  // Field name: goal
  {
    cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_Goal(
      &ros_message->goal, cdr);
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * ros_message)
{
  // Field name: goal_id
  {
    cdr_deserialize_unique_identifier_msgs__msg__UUID(cdr, &ros_message->goal_id);
  }

  // Field name: goal
  {
    cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_Goal(cdr, &ros_message->goal);
  }

  return true;
}  // NOLINT(readability/fn_size)


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_SendGoal_Request__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_SendGoal_Request__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: goal_id
  current_alignment += get_serialized_size_unique_identifier_msgs__msg__UUID(
    &(ros_message->goal_id), current_alignment);

  // Field name: goal
  current_alignment += get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Goal(
    &(ros_message->goal), current_alignment);

  return current_alignment - initial_alignment;
}


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;

  // Field name: goal_id
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_unique_identifier_msgs__msg__UUID(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  // Field name: goal
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Goal(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }


  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request;
    is_plain =
      (
      offsetof(DataType, goal) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: goal_id
  {
    cdr_serialize_key_unique_identifier_msgs__msg__UUID(
      &ros_message->goal_id, cdr);
  }

  // Field name: goal
  {
    cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_Goal(
      &ros_message->goal, cdr);
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_SendGoal_Request__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_SendGoal_Request__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;

  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: goal_id
  current_alignment += get_serialized_size_key_unique_identifier_msgs__msg__UUID(
    &(ros_message->goal_id), current_alignment);

  // Field name: goal
  current_alignment += get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Goal(
    &(ros_message->goal), current_alignment);

  return current_alignment - initial_alignment;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;
  // Field name: goal_id
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_key_unique_identifier_msgs__msg__UUID(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  // Field name: goal
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Goal(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request;
    is_plain =
      (
      offsetof(DataType, goal) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}


static bool _ExecuteSkill_SendGoal_Request__cdr_serialize(
  const void * untyped_ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * ros_message = static_cast<const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request *>(untyped_ros_message);
  (void)ros_message;
  return cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(ros_message, cdr);
}

static bool _ExecuteSkill_SendGoal_Request__cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  void * untyped_ros_message)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * ros_message = static_cast<thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request *>(untyped_ros_message);
  (void)ros_message;
  return cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(cdr, ros_message);
}

static uint32_t _ExecuteSkill_SendGoal_Request__get_serialized_size(const void * untyped_ros_message)
{
  return static_cast<uint32_t>(
    get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
      untyped_ros_message, 0));
}

static size_t _ExecuteSkill_SendGoal_Request__max_serialized_size(char & bounds_info)
{
  bool full_bounded;
  bool is_plain;
  size_t ret_val;

  ret_val = max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
    full_bounded, is_plain, 0);

  bounds_info =
    is_plain ? ROSIDL_TYPESUPPORT_FASTRTPS_PLAIN_TYPE :
    full_bounded ? ROSIDL_TYPESUPPORT_FASTRTPS_BOUNDED_TYPE : ROSIDL_TYPESUPPORT_FASTRTPS_UNBOUNDED_TYPE;
  return ret_val;
}


static message_type_support_callbacks_t __callbacks_ExecuteSkill_SendGoal_Request = {
  "thesis_skill_interfaces::action",
  "ExecuteSkill_SendGoal_Request",
  _ExecuteSkill_SendGoal_Request__cdr_serialize,
  _ExecuteSkill_SendGoal_Request__cdr_deserialize,
  _ExecuteSkill_SendGoal_Request__get_serialized_size,
  _ExecuteSkill_SendGoal_Request__max_serialized_size,
  nullptr
};

static rosidl_message_type_support_t _ExecuteSkill_SendGoal_Request__type_support = {
  rosidl_typesupport_fastrtps_c__identifier,
  &__callbacks_ExecuteSkill_SendGoal_Request,
  get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__get_type_description_sources,
};

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal_Request)() {
  return &_ExecuteSkill_SendGoal_Request__type_support;
}

#if defined(__cplusplus)
}
#endif

// already included above
// #include <cassert>
// already included above
// #include <cstddef>
// already included above
// #include <limits>
// already included above
// #include <string>
// already included above
// #include "rosidl_typesupport_fastrtps_c/identifier.h"
// already included above
// #include "rosidl_typesupport_fastrtps_c/serialization_helpers.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_c/wstring_conversion.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_cpp/message_type_support.h"
// already included above
// #include "thesis_skill_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "fastcdr/Cdr.h"

#ifndef _WIN32
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wunused-parameter"
# ifdef __clang__
#  pragma clang diagnostic ignored "-Wdeprecated-register"
#  pragma clang diagnostic ignored "-Wreturn-type-c-linkage"
# endif
#endif
#ifndef _WIN32
# pragma GCC diagnostic pop
#endif

// includes and forward declarations of message dependencies and their conversion functions

#if defined(__cplusplus)
extern "C"
{
#endif

#include "builtin_interfaces/msg/detail/time__functions.h"  // stamp

// forward declare type support functions

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_serialize_builtin_interfaces__msg__Time(
  const builtin_interfaces__msg__Time * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_deserialize_builtin_interfaces__msg__Time(
  eprosima::fastcdr::Cdr & cdr,
  builtin_interfaces__msg__Time * ros_message);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t get_serialized_size_builtin_interfaces__msg__Time(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t max_serialized_size_builtin_interfaces__msg__Time(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_serialize_key_builtin_interfaces__msg__Time(
  const builtin_interfaces__msg__Time * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t get_serialized_size_key_builtin_interfaces__msg__Time(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t max_serialized_size_key_builtin_interfaces__msg__Time(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
const rosidl_message_type_support_t *
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, builtin_interfaces, msg, Time)();


using _ExecuteSkill_SendGoal_Response__ros_msg_type = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response;


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: accepted
  {
    cdr << (ros_message->accepted ? true : false);
  }

  // Field name: stamp
  {
    cdr_serialize_builtin_interfaces__msg__Time(
      &ros_message->stamp, cdr);
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * ros_message)
{
  // Field name: accepted
  {
    uint8_t tmp;
    cdr >> tmp;
    ros_message->accepted = tmp ? true : false;
  }

  // Field name: stamp
  {
    cdr_deserialize_builtin_interfaces__msg__Time(cdr, &ros_message->stamp);
  }

  return true;
}  // NOLINT(readability/fn_size)


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_SendGoal_Response__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_SendGoal_Response__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: accepted
  {
    size_t item_size = sizeof(ros_message->accepted);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: stamp
  current_alignment += get_serialized_size_builtin_interfaces__msg__Time(
    &(ros_message->stamp), current_alignment);

  return current_alignment - initial_alignment;
}


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;

  // Field name: accepted
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: stamp
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_builtin_interfaces__msg__Time(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }


  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response;
    is_plain =
      (
      offsetof(DataType, stamp) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: accepted
  {
    cdr << (ros_message->accepted ? true : false);
  }

  // Field name: stamp
  {
    cdr_serialize_key_builtin_interfaces__msg__Time(
      &ros_message->stamp, cdr);
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_SendGoal_Response__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_SendGoal_Response__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;

  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: accepted
  {
    size_t item_size = sizeof(ros_message->accepted);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: stamp
  current_alignment += get_serialized_size_key_builtin_interfaces__msg__Time(
    &(ros_message->stamp), current_alignment);

  return current_alignment - initial_alignment;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;
  // Field name: accepted
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: stamp
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_key_builtin_interfaces__msg__Time(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response;
    is_plain =
      (
      offsetof(DataType, stamp) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}


static bool _ExecuteSkill_SendGoal_Response__cdr_serialize(
  const void * untyped_ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * ros_message = static_cast<const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response *>(untyped_ros_message);
  (void)ros_message;
  return cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(ros_message, cdr);
}

static bool _ExecuteSkill_SendGoal_Response__cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  void * untyped_ros_message)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * ros_message = static_cast<thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response *>(untyped_ros_message);
  (void)ros_message;
  return cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(cdr, ros_message);
}

static uint32_t _ExecuteSkill_SendGoal_Response__get_serialized_size(const void * untyped_ros_message)
{
  return static_cast<uint32_t>(
    get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
      untyped_ros_message, 0));
}

static size_t _ExecuteSkill_SendGoal_Response__max_serialized_size(char & bounds_info)
{
  bool full_bounded;
  bool is_plain;
  size_t ret_val;

  ret_val = max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
    full_bounded, is_plain, 0);

  bounds_info =
    is_plain ? ROSIDL_TYPESUPPORT_FASTRTPS_PLAIN_TYPE :
    full_bounded ? ROSIDL_TYPESUPPORT_FASTRTPS_BOUNDED_TYPE : ROSIDL_TYPESUPPORT_FASTRTPS_UNBOUNDED_TYPE;
  return ret_val;
}


static message_type_support_callbacks_t __callbacks_ExecuteSkill_SendGoal_Response = {
  "thesis_skill_interfaces::action",
  "ExecuteSkill_SendGoal_Response",
  _ExecuteSkill_SendGoal_Response__cdr_serialize,
  _ExecuteSkill_SendGoal_Response__cdr_deserialize,
  _ExecuteSkill_SendGoal_Response__get_serialized_size,
  _ExecuteSkill_SendGoal_Response__max_serialized_size,
  nullptr
};

static rosidl_message_type_support_t _ExecuteSkill_SendGoal_Response__type_support = {
  rosidl_typesupport_fastrtps_c__identifier,
  &__callbacks_ExecuteSkill_SendGoal_Response,
  get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__get_type_description_sources,
};

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal_Response)() {
  return &_ExecuteSkill_SendGoal_Response__type_support;
}

#if defined(__cplusplus)
}
#endif

// already included above
// #include <cassert>
// already included above
// #include <cstddef>
// already included above
// #include <limits>
// already included above
// #include <string>
// already included above
// #include "rosidl_typesupport_fastrtps_c/identifier.h"
// already included above
// #include "rosidl_typesupport_fastrtps_c/serialization_helpers.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_c/wstring_conversion.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_cpp/message_type_support.h"
// already included above
// #include "thesis_skill_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "fastcdr/Cdr.h"

#ifndef _WIN32
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wunused-parameter"
# ifdef __clang__
#  pragma clang diagnostic ignored "-Wdeprecated-register"
#  pragma clang diagnostic ignored "-Wreturn-type-c-linkage"
# endif
#endif
#ifndef _WIN32
# pragma GCC diagnostic pop
#endif

// includes and forward declarations of message dependencies and their conversion functions

#if defined(__cplusplus)
extern "C"
{
#endif

#include "service_msgs/msg/detail/service_event_info__functions.h"  // info

// forward declare type support functions

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_serialize_service_msgs__msg__ServiceEventInfo(
  const service_msgs__msg__ServiceEventInfo * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_deserialize_service_msgs__msg__ServiceEventInfo(
  eprosima::fastcdr::Cdr & cdr,
  service_msgs__msg__ServiceEventInfo * ros_message);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t get_serialized_size_service_msgs__msg__ServiceEventInfo(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t max_serialized_size_service_msgs__msg__ServiceEventInfo(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_serialize_key_service_msgs__msg__ServiceEventInfo(
  const service_msgs__msg__ServiceEventInfo * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t get_serialized_size_key_service_msgs__msg__ServiceEventInfo(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t max_serialized_size_key_service_msgs__msg__ServiceEventInfo(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
const rosidl_message_type_support_t *
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, service_msgs, msg, ServiceEventInfo)();

bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * ros_message,
  eprosima::fastcdr::Cdr & cdr);

bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * ros_message);

size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
  const void * untyped_ros_message,
  size_t current_alignment);

size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * ros_message,
  eprosima::fastcdr::Cdr & cdr);

size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
  const void * untyped_ros_message,
  size_t current_alignment);

size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

const rosidl_message_type_support_t *
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal_Request)();

bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * ros_message,
  eprosima::fastcdr::Cdr & cdr);

bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * ros_message);

size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
  const void * untyped_ros_message,
  size_t current_alignment);

size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * ros_message,
  eprosima::fastcdr::Cdr & cdr);

size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
  const void * untyped_ros_message,
  size_t current_alignment);

size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

const rosidl_message_type_support_t *
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal_Response)();


using _ExecuteSkill_SendGoal_Event__ros_msg_type = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event;


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event(
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: info
  {
    cdr_serialize_service_msgs__msg__ServiceEventInfo(
      &ros_message->info, cdr);
  }

  // Field name: request
  {
    size_t size = ros_message->request.size;
    auto array_ptr = ros_message->request.data;
    if (size > 1) {
      fprintf(stderr, "array size exceeds upper bound\n");
      return false;
    }
    cdr << static_cast<uint32_t>(size);
    for (size_t i = 0; i < size; ++i) {
      cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
        &array_ptr[i], cdr);
    }
  }

  // Field name: response
  {
    size_t size = ros_message->response.size;
    auto array_ptr = ros_message->response.data;
    if (size > 1) {
      fprintf(stderr, "array size exceeds upper bound\n");
      return false;
    }
    cdr << static_cast<uint32_t>(size);
    for (size_t i = 0; i < size; ++i) {
      cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
        &array_ptr[i], cdr);
    }
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event * ros_message)
{
  // Field name: info
  {
    cdr_deserialize_service_msgs__msg__ServiceEventInfo(cdr, &ros_message->info);
  }

  // Field name: request
  {
    uint32_t cdrSize;
    cdr >> cdrSize;
    size_t size = static_cast<size_t>(cdrSize);

    // Check there are at least 'size' remaining bytes in the CDR stream before resizing
    auto old_state = cdr.get_state();
    bool correct_size = cdr.jump(size);
    cdr.set_state(old_state);
    if (!correct_size) {
      fprintf(stderr, "sequence size exceeds remaining buffer\n");
      return false;
    }

    if (ros_message->request.data) {
      thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence__fini(&ros_message->request);
    }
    if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence__init(&ros_message->request, size)) {
      fprintf(stderr, "failed to create array for field 'request'");
      return false;
    }
    auto array_ptr = ros_message->request.data;
    for (size_t i = 0; i < size; ++i) {
      cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(cdr, &array_ptr[i]);
    }
  }

  // Field name: response
  {
    uint32_t cdrSize;
    cdr >> cdrSize;
    size_t size = static_cast<size_t>(cdrSize);

    // Check there are at least 'size' remaining bytes in the CDR stream before resizing
    auto old_state = cdr.get_state();
    bool correct_size = cdr.jump(size);
    cdr.set_state(old_state);
    if (!correct_size) {
      fprintf(stderr, "sequence size exceeds remaining buffer\n");
      return false;
    }

    if (ros_message->response.data) {
      thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence__fini(&ros_message->response);
    }
    if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence__init(&ros_message->response, size)) {
      fprintf(stderr, "failed to create array for field 'response'");
      return false;
    }
    auto array_ptr = ros_message->response.data;
    for (size_t i = 0; i < size; ++i) {
      cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(cdr, &array_ptr[i]);
    }
  }

  return true;
}  // NOLINT(readability/fn_size)


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_SendGoal_Event__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_SendGoal_Event__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: info
  current_alignment += get_serialized_size_service_msgs__msg__ServiceEventInfo(
    &(ros_message->info), current_alignment);

  // Field name: request
  {
    size_t array_size = ros_message->request.size;
    auto array_ptr = ros_message->request.data;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
        &array_ptr[index], current_alignment);
    }
  }

  // Field name: response
  {
    size_t array_size = ros_message->response.size;
    auto array_ptr = ros_message->response.data;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
        &array_ptr[index], current_alignment);
    }
  }

  return current_alignment - initial_alignment;
}


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;

  // Field name: info
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_service_msgs__msg__ServiceEventInfo(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  // Field name: request
  {
    size_t array_size = 1;
    is_plain = false;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  // Field name: response
  {
    size_t array_size = 1;
    is_plain = false;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }


  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event;
    is_plain =
      (
      offsetof(DataType, response) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event(
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: info
  {
    cdr_serialize_key_service_msgs__msg__ServiceEventInfo(
      &ros_message->info, cdr);
  }

  // Field name: request
  {
    size_t size = ros_message->request.size;
    auto array_ptr = ros_message->request.data;
    if (size > 1) {
      fprintf(stderr, "array size exceeds upper bound\n");
      return false;
    }
    cdr << static_cast<uint32_t>(size);
    for (size_t i = 0; i < size; ++i) {
      cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
        &array_ptr[i], cdr);
    }
  }

  // Field name: response
  {
    size_t size = ros_message->response.size;
    auto array_ptr = ros_message->response.data;
    if (size > 1) {
      fprintf(stderr, "array size exceeds upper bound\n");
      return false;
    }
    cdr << static_cast<uint32_t>(size);
    for (size_t i = 0; i < size; ++i) {
      cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
        &array_ptr[i], cdr);
    }
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_SendGoal_Event__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_SendGoal_Event__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;

  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: info
  current_alignment += get_serialized_size_key_service_msgs__msg__ServiceEventInfo(
    &(ros_message->info), current_alignment);

  // Field name: request
  {
    size_t array_size = ros_message->request.size;
    auto array_ptr = ros_message->request.data;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
        &array_ptr[index], current_alignment);
    }
  }

  // Field name: response
  {
    size_t array_size = ros_message->response.size;
    auto array_ptr = ros_message->response.data;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
        &array_ptr[index], current_alignment);
    }
  }

  return current_alignment - initial_alignment;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;
  // Field name: info
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_key_service_msgs__msg__ServiceEventInfo(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  // Field name: request
  {
    size_t array_size = 1;
    is_plain = false;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  // Field name: response
  {
    size_t array_size = 1;
    is_plain = false;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event;
    is_plain =
      (
      offsetof(DataType, response) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}


static bool _ExecuteSkill_SendGoal_Event__cdr_serialize(
  const void * untyped_ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event * ros_message = static_cast<const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event *>(untyped_ros_message);
  (void)ros_message;
  return cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event(ros_message, cdr);
}

static bool _ExecuteSkill_SendGoal_Event__cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  void * untyped_ros_message)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event * ros_message = static_cast<thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event *>(untyped_ros_message);
  (void)ros_message;
  return cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event(cdr, ros_message);
}

static uint32_t _ExecuteSkill_SendGoal_Event__get_serialized_size(const void * untyped_ros_message)
{
  return static_cast<uint32_t>(
    get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event(
      untyped_ros_message, 0));
}

static size_t _ExecuteSkill_SendGoal_Event__max_serialized_size(char & bounds_info)
{
  bool full_bounded;
  bool is_plain;
  size_t ret_val;

  ret_val = max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event(
    full_bounded, is_plain, 0);

  bounds_info =
    is_plain ? ROSIDL_TYPESUPPORT_FASTRTPS_PLAIN_TYPE :
    full_bounded ? ROSIDL_TYPESUPPORT_FASTRTPS_BOUNDED_TYPE : ROSIDL_TYPESUPPORT_FASTRTPS_UNBOUNDED_TYPE;
  return ret_val;
}


static message_type_support_callbacks_t __callbacks_ExecuteSkill_SendGoal_Event = {
  "thesis_skill_interfaces::action",
  "ExecuteSkill_SendGoal_Event",
  _ExecuteSkill_SendGoal_Event__cdr_serialize,
  _ExecuteSkill_SendGoal_Event__cdr_deserialize,
  _ExecuteSkill_SendGoal_Event__get_serialized_size,
  _ExecuteSkill_SendGoal_Event__max_serialized_size,
  nullptr
};

static rosidl_message_type_support_t _ExecuteSkill_SendGoal_Event__type_support = {
  rosidl_typesupport_fastrtps_c__identifier,
  &__callbacks_ExecuteSkill_SendGoal_Event,
  get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__get_type_description_sources,
};

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal_Event)() {
  return &_ExecuteSkill_SendGoal_Event__type_support;
}

#if defined(__cplusplus)
}
#endif

#include "rosidl_typesupport_fastrtps_cpp/service_type_support.h"
#include "rosidl_typesupport_cpp/service_type_support.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_c/identifier.h"
// already included above
// #include "thesis_skill_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
#include "thesis_skill_interfaces/action/execute_skill.h"

#if defined(__cplusplus)
extern "C"
{
#endif

static service_type_support_callbacks_t ExecuteSkill_SendGoal__callbacks = {
  "thesis_skill_interfaces::action",
  "ExecuteSkill_SendGoal",
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal_Request)(),
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal_Response)(),
};

static rosidl_service_type_support_t ExecuteSkill_SendGoal__handle = {
  rosidl_typesupport_fastrtps_c__identifier,
  &ExecuteSkill_SendGoal__callbacks,
  get_service_typesupport_handle_function,
  &_ExecuteSkill_SendGoal_Request__type_support,
  &_ExecuteSkill_SendGoal_Response__type_support,
  &_ExecuteSkill_SendGoal_Event__type_support,
  ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_CREATE_EVENT_MESSAGE_SYMBOL_NAME(
    rosidl_typesupport_c,
    thesis_skill_interfaces,
    action,
    ExecuteSkill_SendGoal
  ),
  ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_DESTROY_EVENT_MESSAGE_SYMBOL_NAME(
    rosidl_typesupport_c,
    thesis_skill_interfaces,
    action,
    ExecuteSkill_SendGoal
  ),
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal__get_type_description_sources,
};

const rosidl_service_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal)() {
  return &ExecuteSkill_SendGoal__handle;
}

#if defined(__cplusplus)
}
#endif

// already included above
// #include <cassert>
// already included above
// #include <cstddef>
// already included above
// #include <limits>
// already included above
// #include <string>
// already included above
// #include "rosidl_typesupport_fastrtps_c/identifier.h"
// already included above
// #include "rosidl_typesupport_fastrtps_c/serialization_helpers.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_c/wstring_conversion.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_cpp/message_type_support.h"
// already included above
// #include "thesis_skill_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "fastcdr/Cdr.h"

#ifndef _WIN32
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wunused-parameter"
# ifdef __clang__
#  pragma clang diagnostic ignored "-Wdeprecated-register"
#  pragma clang diagnostic ignored "-Wreturn-type-c-linkage"
# endif
#endif
#ifndef _WIN32
# pragma GCC diagnostic pop
#endif

// includes and forward declarations of message dependencies and their conversion functions

#if defined(__cplusplus)
extern "C"
{
#endif

// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__functions.h"  // goal_id

// forward declare type support functions

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_serialize_unique_identifier_msgs__msg__UUID(
  const unique_identifier_msgs__msg__UUID * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_deserialize_unique_identifier_msgs__msg__UUID(
  eprosima::fastcdr::Cdr & cdr,
  unique_identifier_msgs__msg__UUID * ros_message);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t get_serialized_size_unique_identifier_msgs__msg__UUID(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t max_serialized_size_unique_identifier_msgs__msg__UUID(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_serialize_key_unique_identifier_msgs__msg__UUID(
  const unique_identifier_msgs__msg__UUID * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t get_serialized_size_key_unique_identifier_msgs__msg__UUID(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t max_serialized_size_key_unique_identifier_msgs__msg__UUID(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
const rosidl_message_type_support_t *
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, unique_identifier_msgs, msg, UUID)();


using _ExecuteSkill_GetResult_Request__ros_msg_type = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request;


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: goal_id
  {
    cdr_serialize_unique_identifier_msgs__msg__UUID(
      &ros_message->goal_id, cdr);
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * ros_message)
{
  // Field name: goal_id
  {
    cdr_deserialize_unique_identifier_msgs__msg__UUID(cdr, &ros_message->goal_id);
  }

  return true;
}  // NOLINT(readability/fn_size)


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_GetResult_Request__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_GetResult_Request__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: goal_id
  current_alignment += get_serialized_size_unique_identifier_msgs__msg__UUID(
    &(ros_message->goal_id), current_alignment);

  return current_alignment - initial_alignment;
}


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;

  // Field name: goal_id
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_unique_identifier_msgs__msg__UUID(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }


  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request;
    is_plain =
      (
      offsetof(DataType, goal_id) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: goal_id
  {
    cdr_serialize_key_unique_identifier_msgs__msg__UUID(
      &ros_message->goal_id, cdr);
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_GetResult_Request__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_GetResult_Request__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;

  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: goal_id
  current_alignment += get_serialized_size_key_unique_identifier_msgs__msg__UUID(
    &(ros_message->goal_id), current_alignment);

  return current_alignment - initial_alignment;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;
  // Field name: goal_id
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_key_unique_identifier_msgs__msg__UUID(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request;
    is_plain =
      (
      offsetof(DataType, goal_id) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}


static bool _ExecuteSkill_GetResult_Request__cdr_serialize(
  const void * untyped_ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * ros_message = static_cast<const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request *>(untyped_ros_message);
  (void)ros_message;
  return cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(ros_message, cdr);
}

static bool _ExecuteSkill_GetResult_Request__cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  void * untyped_ros_message)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * ros_message = static_cast<thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request *>(untyped_ros_message);
  (void)ros_message;
  return cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(cdr, ros_message);
}

static uint32_t _ExecuteSkill_GetResult_Request__get_serialized_size(const void * untyped_ros_message)
{
  return static_cast<uint32_t>(
    get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
      untyped_ros_message, 0));
}

static size_t _ExecuteSkill_GetResult_Request__max_serialized_size(char & bounds_info)
{
  bool full_bounded;
  bool is_plain;
  size_t ret_val;

  ret_val = max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
    full_bounded, is_plain, 0);

  bounds_info =
    is_plain ? ROSIDL_TYPESUPPORT_FASTRTPS_PLAIN_TYPE :
    full_bounded ? ROSIDL_TYPESUPPORT_FASTRTPS_BOUNDED_TYPE : ROSIDL_TYPESUPPORT_FASTRTPS_UNBOUNDED_TYPE;
  return ret_val;
}


static message_type_support_callbacks_t __callbacks_ExecuteSkill_GetResult_Request = {
  "thesis_skill_interfaces::action",
  "ExecuteSkill_GetResult_Request",
  _ExecuteSkill_GetResult_Request__cdr_serialize,
  _ExecuteSkill_GetResult_Request__cdr_deserialize,
  _ExecuteSkill_GetResult_Request__get_serialized_size,
  _ExecuteSkill_GetResult_Request__max_serialized_size,
  nullptr
};

static rosidl_message_type_support_t _ExecuteSkill_GetResult_Request__type_support = {
  rosidl_typesupport_fastrtps_c__identifier,
  &__callbacks_ExecuteSkill_GetResult_Request,
  get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__get_type_description_sources,
};

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult_Request)() {
  return &_ExecuteSkill_GetResult_Request__type_support;
}

#if defined(__cplusplus)
}
#endif

// already included above
// #include <cassert>
// already included above
// #include <cstddef>
// already included above
// #include <limits>
// already included above
// #include <string>
// already included above
// #include "rosidl_typesupport_fastrtps_c/identifier.h"
// already included above
// #include "rosidl_typesupport_fastrtps_c/serialization_helpers.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_c/wstring_conversion.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_cpp/message_type_support.h"
// already included above
// #include "thesis_skill_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "fastcdr/Cdr.h"

#ifndef _WIN32
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wunused-parameter"
# ifdef __clang__
#  pragma clang diagnostic ignored "-Wdeprecated-register"
#  pragma clang diagnostic ignored "-Wreturn-type-c-linkage"
# endif
#endif
#ifndef _WIN32
# pragma GCC diagnostic pop
#endif

// includes and forward declarations of message dependencies and their conversion functions

#if defined(__cplusplus)
extern "C"
{
#endif

// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"  // result

// forward declare type support functions

bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_Result(
  const thesis_skill_interfaces__action__ExecuteSkill_Result * ros_message,
  eprosima::fastcdr::Cdr & cdr);

bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_Result(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_Result * ros_message);

size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Result(
  const void * untyped_ros_message,
  size_t current_alignment);

size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Result(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_Result(
  const thesis_skill_interfaces__action__ExecuteSkill_Result * ros_message,
  eprosima::fastcdr::Cdr & cdr);

size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Result(
  const void * untyped_ros_message,
  size_t current_alignment);

size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Result(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

const rosidl_message_type_support_t *
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_Result)();


using _ExecuteSkill_GetResult_Response__ros_msg_type = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response;


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: status
  {
    cdr << ros_message->status;
  }

  // Field name: result
  {
    cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_Result(
      &ros_message->result, cdr);
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * ros_message)
{
  // Field name: status
  {
    cdr >> ros_message->status;
  }

  // Field name: result
  {
    cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_Result(cdr, &ros_message->result);
  }

  return true;
}  // NOLINT(readability/fn_size)


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_GetResult_Response__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_GetResult_Response__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: status
  {
    size_t item_size = sizeof(ros_message->status);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: result
  current_alignment += get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Result(
    &(ros_message->result), current_alignment);

  return current_alignment - initial_alignment;
}


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;

  // Field name: status
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: result
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Result(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }


  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response;
    is_plain =
      (
      offsetof(DataType, result) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: status
  {
    cdr << ros_message->status;
  }

  // Field name: result
  {
    cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_Result(
      &ros_message->result, cdr);
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_GetResult_Response__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_GetResult_Response__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;

  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: status
  {
    size_t item_size = sizeof(ros_message->status);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: result
  current_alignment += get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Result(
    &(ros_message->result), current_alignment);

  return current_alignment - initial_alignment;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;
  // Field name: status
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: result
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Result(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response;
    is_plain =
      (
      offsetof(DataType, result) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}


static bool _ExecuteSkill_GetResult_Response__cdr_serialize(
  const void * untyped_ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * ros_message = static_cast<const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response *>(untyped_ros_message);
  (void)ros_message;
  return cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(ros_message, cdr);
}

static bool _ExecuteSkill_GetResult_Response__cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  void * untyped_ros_message)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * ros_message = static_cast<thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response *>(untyped_ros_message);
  (void)ros_message;
  return cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(cdr, ros_message);
}

static uint32_t _ExecuteSkill_GetResult_Response__get_serialized_size(const void * untyped_ros_message)
{
  return static_cast<uint32_t>(
    get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
      untyped_ros_message, 0));
}

static size_t _ExecuteSkill_GetResult_Response__max_serialized_size(char & bounds_info)
{
  bool full_bounded;
  bool is_plain;
  size_t ret_val;

  ret_val = max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
    full_bounded, is_plain, 0);

  bounds_info =
    is_plain ? ROSIDL_TYPESUPPORT_FASTRTPS_PLAIN_TYPE :
    full_bounded ? ROSIDL_TYPESUPPORT_FASTRTPS_BOUNDED_TYPE : ROSIDL_TYPESUPPORT_FASTRTPS_UNBOUNDED_TYPE;
  return ret_val;
}


static message_type_support_callbacks_t __callbacks_ExecuteSkill_GetResult_Response = {
  "thesis_skill_interfaces::action",
  "ExecuteSkill_GetResult_Response",
  _ExecuteSkill_GetResult_Response__cdr_serialize,
  _ExecuteSkill_GetResult_Response__cdr_deserialize,
  _ExecuteSkill_GetResult_Response__get_serialized_size,
  _ExecuteSkill_GetResult_Response__max_serialized_size,
  nullptr
};

static rosidl_message_type_support_t _ExecuteSkill_GetResult_Response__type_support = {
  rosidl_typesupport_fastrtps_c__identifier,
  &__callbacks_ExecuteSkill_GetResult_Response,
  get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__get_type_description_sources,
};

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult_Response)() {
  return &_ExecuteSkill_GetResult_Response__type_support;
}

#if defined(__cplusplus)
}
#endif

// already included above
// #include <cassert>
// already included above
// #include <cstddef>
// already included above
// #include <limits>
// already included above
// #include <string>
// already included above
// #include "rosidl_typesupport_fastrtps_c/identifier.h"
// already included above
// #include "rosidl_typesupport_fastrtps_c/serialization_helpers.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_c/wstring_conversion.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_cpp/message_type_support.h"
// already included above
// #include "thesis_skill_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "fastcdr/Cdr.h"

#ifndef _WIN32
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wunused-parameter"
# ifdef __clang__
#  pragma clang diagnostic ignored "-Wdeprecated-register"
#  pragma clang diagnostic ignored "-Wreturn-type-c-linkage"
# endif
#endif
#ifndef _WIN32
# pragma GCC diagnostic pop
#endif

// includes and forward declarations of message dependencies and their conversion functions

#if defined(__cplusplus)
extern "C"
{
#endif

// already included above
// #include "service_msgs/msg/detail/service_event_info__functions.h"  // info

// forward declare type support functions

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_serialize_service_msgs__msg__ServiceEventInfo(
  const service_msgs__msg__ServiceEventInfo * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_deserialize_service_msgs__msg__ServiceEventInfo(
  eprosima::fastcdr::Cdr & cdr,
  service_msgs__msg__ServiceEventInfo * ros_message);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t get_serialized_size_service_msgs__msg__ServiceEventInfo(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t max_serialized_size_service_msgs__msg__ServiceEventInfo(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_serialize_key_service_msgs__msg__ServiceEventInfo(
  const service_msgs__msg__ServiceEventInfo * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t get_serialized_size_key_service_msgs__msg__ServiceEventInfo(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t max_serialized_size_key_service_msgs__msg__ServiceEventInfo(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
const rosidl_message_type_support_t *
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, service_msgs, msg, ServiceEventInfo)();

bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * ros_message,
  eprosima::fastcdr::Cdr & cdr);

bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * ros_message);

size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
  const void * untyped_ros_message,
  size_t current_alignment);

size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * ros_message,
  eprosima::fastcdr::Cdr & cdr);

size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
  const void * untyped_ros_message,
  size_t current_alignment);

size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

const rosidl_message_type_support_t *
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult_Request)();

bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * ros_message,
  eprosima::fastcdr::Cdr & cdr);

bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * ros_message);

size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
  const void * untyped_ros_message,
  size_t current_alignment);

size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * ros_message,
  eprosima::fastcdr::Cdr & cdr);

size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
  const void * untyped_ros_message,
  size_t current_alignment);

size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

const rosidl_message_type_support_t *
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult_Response)();


using _ExecuteSkill_GetResult_Event__ros_msg_type = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event;


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event(
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: info
  {
    cdr_serialize_service_msgs__msg__ServiceEventInfo(
      &ros_message->info, cdr);
  }

  // Field name: request
  {
    size_t size = ros_message->request.size;
    auto array_ptr = ros_message->request.data;
    if (size > 1) {
      fprintf(stderr, "array size exceeds upper bound\n");
      return false;
    }
    cdr << static_cast<uint32_t>(size);
    for (size_t i = 0; i < size; ++i) {
      cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
        &array_ptr[i], cdr);
    }
  }

  // Field name: response
  {
    size_t size = ros_message->response.size;
    auto array_ptr = ros_message->response.data;
    if (size > 1) {
      fprintf(stderr, "array size exceeds upper bound\n");
      return false;
    }
    cdr << static_cast<uint32_t>(size);
    for (size_t i = 0; i < size; ++i) {
      cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
        &array_ptr[i], cdr);
    }
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event * ros_message)
{
  // Field name: info
  {
    cdr_deserialize_service_msgs__msg__ServiceEventInfo(cdr, &ros_message->info);
  }

  // Field name: request
  {
    uint32_t cdrSize;
    cdr >> cdrSize;
    size_t size = static_cast<size_t>(cdrSize);

    // Check there are at least 'size' remaining bytes in the CDR stream before resizing
    auto old_state = cdr.get_state();
    bool correct_size = cdr.jump(size);
    cdr.set_state(old_state);
    if (!correct_size) {
      fprintf(stderr, "sequence size exceeds remaining buffer\n");
      return false;
    }

    if (ros_message->request.data) {
      thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence__fini(&ros_message->request);
    }
    if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence__init(&ros_message->request, size)) {
      fprintf(stderr, "failed to create array for field 'request'");
      return false;
    }
    auto array_ptr = ros_message->request.data;
    for (size_t i = 0; i < size; ++i) {
      cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(cdr, &array_ptr[i]);
    }
  }

  // Field name: response
  {
    uint32_t cdrSize;
    cdr >> cdrSize;
    size_t size = static_cast<size_t>(cdrSize);

    // Check there are at least 'size' remaining bytes in the CDR stream before resizing
    auto old_state = cdr.get_state();
    bool correct_size = cdr.jump(size);
    cdr.set_state(old_state);
    if (!correct_size) {
      fprintf(stderr, "sequence size exceeds remaining buffer\n");
      return false;
    }

    if (ros_message->response.data) {
      thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence__fini(&ros_message->response);
    }
    if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence__init(&ros_message->response, size)) {
      fprintf(stderr, "failed to create array for field 'response'");
      return false;
    }
    auto array_ptr = ros_message->response.data;
    for (size_t i = 0; i < size; ++i) {
      cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(cdr, &array_ptr[i]);
    }
  }

  return true;
}  // NOLINT(readability/fn_size)


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_GetResult_Event__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_GetResult_Event__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: info
  current_alignment += get_serialized_size_service_msgs__msg__ServiceEventInfo(
    &(ros_message->info), current_alignment);

  // Field name: request
  {
    size_t array_size = ros_message->request.size;
    auto array_ptr = ros_message->request.data;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
        &array_ptr[index], current_alignment);
    }
  }

  // Field name: response
  {
    size_t array_size = ros_message->response.size;
    auto array_ptr = ros_message->response.data;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
        &array_ptr[index], current_alignment);
    }
  }

  return current_alignment - initial_alignment;
}


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;

  // Field name: info
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_service_msgs__msg__ServiceEventInfo(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  // Field name: request
  {
    size_t array_size = 1;
    is_plain = false;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  // Field name: response
  {
    size_t array_size = 1;
    is_plain = false;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }


  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event;
    is_plain =
      (
      offsetof(DataType, response) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event(
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: info
  {
    cdr_serialize_key_service_msgs__msg__ServiceEventInfo(
      &ros_message->info, cdr);
  }

  // Field name: request
  {
    size_t size = ros_message->request.size;
    auto array_ptr = ros_message->request.data;
    if (size > 1) {
      fprintf(stderr, "array size exceeds upper bound\n");
      return false;
    }
    cdr << static_cast<uint32_t>(size);
    for (size_t i = 0; i < size; ++i) {
      cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
        &array_ptr[i], cdr);
    }
  }

  // Field name: response
  {
    size_t size = ros_message->response.size;
    auto array_ptr = ros_message->response.data;
    if (size > 1) {
      fprintf(stderr, "array size exceeds upper bound\n");
      return false;
    }
    cdr << static_cast<uint32_t>(size);
    for (size_t i = 0; i < size; ++i) {
      cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
        &array_ptr[i], cdr);
    }
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_GetResult_Event__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_GetResult_Event__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;

  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: info
  current_alignment += get_serialized_size_key_service_msgs__msg__ServiceEventInfo(
    &(ros_message->info), current_alignment);

  // Field name: request
  {
    size_t array_size = ros_message->request.size;
    auto array_ptr = ros_message->request.data;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
        &array_ptr[index], current_alignment);
    }
  }

  // Field name: response
  {
    size_t array_size = ros_message->response.size;
    auto array_ptr = ros_message->response.data;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
        &array_ptr[index], current_alignment);
    }
  }

  return current_alignment - initial_alignment;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;
  // Field name: info
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_key_service_msgs__msg__ServiceEventInfo(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  // Field name: request
  {
    size_t array_size = 1;
    is_plain = false;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  // Field name: response
  {
    size_t array_size = 1;
    is_plain = false;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event;
    is_plain =
      (
      offsetof(DataType, response) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}


static bool _ExecuteSkill_GetResult_Event__cdr_serialize(
  const void * untyped_ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event * ros_message = static_cast<const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event *>(untyped_ros_message);
  (void)ros_message;
  return cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event(ros_message, cdr);
}

static bool _ExecuteSkill_GetResult_Event__cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  void * untyped_ros_message)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event * ros_message = static_cast<thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event *>(untyped_ros_message);
  (void)ros_message;
  return cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event(cdr, ros_message);
}

static uint32_t _ExecuteSkill_GetResult_Event__get_serialized_size(const void * untyped_ros_message)
{
  return static_cast<uint32_t>(
    get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event(
      untyped_ros_message, 0));
}

static size_t _ExecuteSkill_GetResult_Event__max_serialized_size(char & bounds_info)
{
  bool full_bounded;
  bool is_plain;
  size_t ret_val;

  ret_val = max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event(
    full_bounded, is_plain, 0);

  bounds_info =
    is_plain ? ROSIDL_TYPESUPPORT_FASTRTPS_PLAIN_TYPE :
    full_bounded ? ROSIDL_TYPESUPPORT_FASTRTPS_BOUNDED_TYPE : ROSIDL_TYPESUPPORT_FASTRTPS_UNBOUNDED_TYPE;
  return ret_val;
}


static message_type_support_callbacks_t __callbacks_ExecuteSkill_GetResult_Event = {
  "thesis_skill_interfaces::action",
  "ExecuteSkill_GetResult_Event",
  _ExecuteSkill_GetResult_Event__cdr_serialize,
  _ExecuteSkill_GetResult_Event__cdr_deserialize,
  _ExecuteSkill_GetResult_Event__get_serialized_size,
  _ExecuteSkill_GetResult_Event__max_serialized_size,
  nullptr
};

static rosidl_message_type_support_t _ExecuteSkill_GetResult_Event__type_support = {
  rosidl_typesupport_fastrtps_c__identifier,
  &__callbacks_ExecuteSkill_GetResult_Event,
  get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__get_type_description_sources,
};

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult_Event)() {
  return &_ExecuteSkill_GetResult_Event__type_support;
}

#if defined(__cplusplus)
}
#endif

// already included above
// #include "rosidl_typesupport_fastrtps_cpp/service_type_support.h"
// already included above
// #include "rosidl_typesupport_cpp/service_type_support.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_c/identifier.h"
// already included above
// #include "thesis_skill_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
// already included above
// #include "thesis_skill_interfaces/action/execute_skill.h"

#if defined(__cplusplus)
extern "C"
{
#endif

static service_type_support_callbacks_t ExecuteSkill_GetResult__callbacks = {
  "thesis_skill_interfaces::action",
  "ExecuteSkill_GetResult",
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult_Request)(),
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult_Response)(),
};

static rosidl_service_type_support_t ExecuteSkill_GetResult__handle = {
  rosidl_typesupport_fastrtps_c__identifier,
  &ExecuteSkill_GetResult__callbacks,
  get_service_typesupport_handle_function,
  &_ExecuteSkill_GetResult_Request__type_support,
  &_ExecuteSkill_GetResult_Response__type_support,
  &_ExecuteSkill_GetResult_Event__type_support,
  ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_CREATE_EVENT_MESSAGE_SYMBOL_NAME(
    rosidl_typesupport_c,
    thesis_skill_interfaces,
    action,
    ExecuteSkill_GetResult
  ),
  ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_DESTROY_EVENT_MESSAGE_SYMBOL_NAME(
    rosidl_typesupport_c,
    thesis_skill_interfaces,
    action,
    ExecuteSkill_GetResult
  ),
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult__get_type_description_sources,
};

const rosidl_service_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult)() {
  return &ExecuteSkill_GetResult__handle;
}

#if defined(__cplusplus)
}
#endif

// already included above
// #include <cassert>
// already included above
// #include <cstddef>
// already included above
// #include <limits>
// already included above
// #include <string>
// already included above
// #include "rosidl_typesupport_fastrtps_c/identifier.h"
// already included above
// #include "rosidl_typesupport_fastrtps_c/serialization_helpers.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_c/wstring_conversion.hpp"
// already included above
// #include "rosidl_typesupport_fastrtps_cpp/message_type_support.h"
// already included above
// #include "thesis_skill_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "fastcdr/Cdr.h"

#ifndef _WIN32
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wunused-parameter"
# ifdef __clang__
#  pragma clang diagnostic ignored "-Wdeprecated-register"
#  pragma clang diagnostic ignored "-Wreturn-type-c-linkage"
# endif
#endif
#ifndef _WIN32
# pragma GCC diagnostic pop
#endif

// includes and forward declarations of message dependencies and their conversion functions

#if defined(__cplusplus)
extern "C"
{
#endif

// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"  // feedback
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__functions.h"  // goal_id

// forward declare type support functions

bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
  const thesis_skill_interfaces__action__ExecuteSkill_Feedback * ros_message,
  eprosima::fastcdr::Cdr & cdr);

bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_Feedback * ros_message);

size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
  const void * untyped_ros_message,
  size_t current_alignment);

size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
  const thesis_skill_interfaces__action__ExecuteSkill_Feedback * ros_message,
  eprosima::fastcdr::Cdr & cdr);

size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
  const void * untyped_ros_message,
  size_t current_alignment);

size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

const rosidl_message_type_support_t *
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_Feedback)();

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_serialize_unique_identifier_msgs__msg__UUID(
  const unique_identifier_msgs__msg__UUID * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_deserialize_unique_identifier_msgs__msg__UUID(
  eprosima::fastcdr::Cdr & cdr,
  unique_identifier_msgs__msg__UUID * ros_message);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t get_serialized_size_unique_identifier_msgs__msg__UUID(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t max_serialized_size_unique_identifier_msgs__msg__UUID(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
bool cdr_serialize_key_unique_identifier_msgs__msg__UUID(
  const unique_identifier_msgs__msg__UUID * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t get_serialized_size_key_unique_identifier_msgs__msg__UUID(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
size_t max_serialized_size_key_unique_identifier_msgs__msg__UUID(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_IMPORT_thesis_skill_interfaces
const rosidl_message_type_support_t *
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, unique_identifier_msgs, msg, UUID)();


using _ExecuteSkill_FeedbackMessage__ros_msg_type = thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage;


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage(
  const thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: goal_id
  {
    cdr_serialize_unique_identifier_msgs__msg__UUID(
      &ros_message->goal_id, cdr);
  }

  // Field name: feedback
  {
    cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
      &ros_message->feedback, cdr);
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage(
  eprosima::fastcdr::Cdr & cdr,
  thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage * ros_message)
{
  // Field name: goal_id
  {
    cdr_deserialize_unique_identifier_msgs__msg__UUID(cdr, &ros_message->goal_id);
  }

  // Field name: feedback
  {
    cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_Feedback(cdr, &ros_message->feedback);
  }

  return true;
}  // NOLINT(readability/fn_size)


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_FeedbackMessage__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_FeedbackMessage__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: goal_id
  current_alignment += get_serialized_size_unique_identifier_msgs__msg__UUID(
    &(ros_message->goal_id), current_alignment);

  // Field name: feedback
  current_alignment += get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
    &(ros_message->feedback), current_alignment);

  return current_alignment - initial_alignment;
}


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;

  // Field name: goal_id
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_unique_identifier_msgs__msg__UUID(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  // Field name: feedback
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }


  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage;
    is_plain =
      (
      offsetof(DataType, feedback) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
bool cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage(
  const thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: goal_id
  {
    cdr_serialize_key_unique_identifier_msgs__msg__UUID(
      &ros_message->goal_id, cdr);
  }

  // Field name: feedback
  {
    cdr_serialize_key_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
      &ros_message->feedback, cdr);
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _ExecuteSkill_FeedbackMessage__ros_msg_type * ros_message = static_cast<const _ExecuteSkill_FeedbackMessage__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;

  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: goal_id
  current_alignment += get_serialized_size_key_unique_identifier_msgs__msg__UUID(
    &(ros_message->goal_id), current_alignment);

  // Field name: feedback
  current_alignment += get_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
    &(ros_message->feedback), current_alignment);

  return current_alignment - initial_alignment;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_thesis_skill_interfaces
size_t max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;
  // Field name: goal_id
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_key_unique_identifier_msgs__msg__UUID(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  // Field name: feedback
  {
    size_t array_size = 1;
    last_member_size = 0;
    for (size_t index = 0; index < array_size; ++index) {
      bool inner_full_bounded;
      bool inner_is_plain;
      size_t inner_size;
      inner_size =
        max_serialized_size_key_thesis_skill_interfaces__action__ExecuteSkill_Feedback(
        inner_full_bounded, inner_is_plain, current_alignment);
      last_member_size += inner_size;
      current_alignment += inner_size;
      full_bounded &= inner_full_bounded;
      is_plain &= inner_is_plain;
    }
  }

  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage;
    is_plain =
      (
      offsetof(DataType, feedback) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}


static bool _ExecuteSkill_FeedbackMessage__cdr_serialize(
  const void * untyped_ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  const thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage * ros_message = static_cast<const thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage *>(untyped_ros_message);
  (void)ros_message;
  return cdr_serialize_thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage(ros_message, cdr);
}

static bool _ExecuteSkill_FeedbackMessage__cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  void * untyped_ros_message)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage * ros_message = static_cast<thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage *>(untyped_ros_message);
  (void)ros_message;
  return cdr_deserialize_thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage(cdr, ros_message);
}

static uint32_t _ExecuteSkill_FeedbackMessage__get_serialized_size(const void * untyped_ros_message)
{
  return static_cast<uint32_t>(
    get_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage(
      untyped_ros_message, 0));
}

static size_t _ExecuteSkill_FeedbackMessage__max_serialized_size(char & bounds_info)
{
  bool full_bounded;
  bool is_plain;
  size_t ret_val;

  ret_val = max_serialized_size_thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage(
    full_bounded, is_plain, 0);

  bounds_info =
    is_plain ? ROSIDL_TYPESUPPORT_FASTRTPS_PLAIN_TYPE :
    full_bounded ? ROSIDL_TYPESUPPORT_FASTRTPS_BOUNDED_TYPE : ROSIDL_TYPESUPPORT_FASTRTPS_UNBOUNDED_TYPE;
  return ret_val;
}


static message_type_support_callbacks_t __callbacks_ExecuteSkill_FeedbackMessage = {
  "thesis_skill_interfaces::action",
  "ExecuteSkill_FeedbackMessage",
  _ExecuteSkill_FeedbackMessage__cdr_serialize,
  _ExecuteSkill_FeedbackMessage__cdr_deserialize,
  _ExecuteSkill_FeedbackMessage__get_serialized_size,
  _ExecuteSkill_FeedbackMessage__max_serialized_size,
  nullptr
};

static rosidl_message_type_support_t _ExecuteSkill_FeedbackMessage__type_support = {
  rosidl_typesupport_fastrtps_c__identifier,
  &__callbacks_ExecuteSkill_FeedbackMessage,
  get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__get_type_description_sources,
};

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_FeedbackMessage)() {
  return &_ExecuteSkill_FeedbackMessage__type_support;
}

#if defined(__cplusplus)
}
#endif
