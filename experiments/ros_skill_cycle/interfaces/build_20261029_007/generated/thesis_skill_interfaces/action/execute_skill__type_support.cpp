// generated from rosidl_typesupport_c/resource/idl__type_support.cpp.em
// with input from thesis_skill_interfaces:action/ExecuteSkill.idl
// generated code does not contain a copyright notice

#include "cstddef"
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
#include "thesis_skill_interfaces/action/detail/execute_skill__type_support.h"
#include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
#include "rosidl_typesupport_c/identifier.h"
#include "rosidl_typesupport_c/message_type_support_dispatch.h"
#include "rosidl_typesupport_c/type_support_map.h"
#include "rosidl_typesupport_c/visibility_control.h"
#include "rosidl_typesupport_interface/macros.h"

namespace thesis_skill_interfaces
{

namespace action
{

namespace rosidl_typesupport_c
{

typedef struct _ExecuteSkill_Goal_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _ExecuteSkill_Goal_type_support_ids_t;

static const _ExecuteSkill_Goal_type_support_ids_t _ExecuteSkill_Goal_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _ExecuteSkill_Goal_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _ExecuteSkill_Goal_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _ExecuteSkill_Goal_type_support_symbol_names_t _ExecuteSkill_Goal_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_Goal)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, thesis_skill_interfaces, action, ExecuteSkill_Goal)),
  }
};

typedef struct _ExecuteSkill_Goal_type_support_data_t
{
  void * data[2];
} _ExecuteSkill_Goal_type_support_data_t;

static _ExecuteSkill_Goal_type_support_data_t _ExecuteSkill_Goal_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _ExecuteSkill_Goal_message_typesupport_map = {
  2,
  "thesis_skill_interfaces",
  &_ExecuteSkill_Goal_message_typesupport_ids.typesupport_identifier[0],
  &_ExecuteSkill_Goal_message_typesupport_symbol_names.symbol_name[0],
  &_ExecuteSkill_Goal_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t ExecuteSkill_Goal_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_ExecuteSkill_Goal_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_Goal__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_Goal__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_Goal__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace action

}  // namespace thesis_skill_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, thesis_skill_interfaces, action, ExecuteSkill_Goal)() {
  return &::thesis_skill_interfaces::action::rosidl_typesupport_c::ExecuteSkill_Goal_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
// already included above
// #include "rosidl_runtime_c/message_type_support_struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__type_support.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
// already included above
// #include "rosidl_typesupport_c/message_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_c/visibility_control.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"

namespace thesis_skill_interfaces
{

namespace action
{

namespace rosidl_typesupport_c
{

typedef struct _ExecuteSkill_Result_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _ExecuteSkill_Result_type_support_ids_t;

static const _ExecuteSkill_Result_type_support_ids_t _ExecuteSkill_Result_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _ExecuteSkill_Result_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _ExecuteSkill_Result_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _ExecuteSkill_Result_type_support_symbol_names_t _ExecuteSkill_Result_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_Result)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, thesis_skill_interfaces, action, ExecuteSkill_Result)),
  }
};

typedef struct _ExecuteSkill_Result_type_support_data_t
{
  void * data[2];
} _ExecuteSkill_Result_type_support_data_t;

static _ExecuteSkill_Result_type_support_data_t _ExecuteSkill_Result_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _ExecuteSkill_Result_message_typesupport_map = {
  2,
  "thesis_skill_interfaces",
  &_ExecuteSkill_Result_message_typesupport_ids.typesupport_identifier[0],
  &_ExecuteSkill_Result_message_typesupport_symbol_names.symbol_name[0],
  &_ExecuteSkill_Result_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t ExecuteSkill_Result_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_ExecuteSkill_Result_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_Result__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_Result__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_Result__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace action

}  // namespace thesis_skill_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, thesis_skill_interfaces, action, ExecuteSkill_Result)() {
  return &::thesis_skill_interfaces::action::rosidl_typesupport_c::ExecuteSkill_Result_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
// already included above
// #include "rosidl_runtime_c/message_type_support_struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__type_support.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
// already included above
// #include "rosidl_typesupport_c/message_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_c/visibility_control.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"

namespace thesis_skill_interfaces
{

namespace action
{

namespace rosidl_typesupport_c
{

typedef struct _ExecuteSkill_Feedback_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _ExecuteSkill_Feedback_type_support_ids_t;

static const _ExecuteSkill_Feedback_type_support_ids_t _ExecuteSkill_Feedback_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _ExecuteSkill_Feedback_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _ExecuteSkill_Feedback_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _ExecuteSkill_Feedback_type_support_symbol_names_t _ExecuteSkill_Feedback_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_Feedback)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, thesis_skill_interfaces, action, ExecuteSkill_Feedback)),
  }
};

typedef struct _ExecuteSkill_Feedback_type_support_data_t
{
  void * data[2];
} _ExecuteSkill_Feedback_type_support_data_t;

static _ExecuteSkill_Feedback_type_support_data_t _ExecuteSkill_Feedback_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _ExecuteSkill_Feedback_message_typesupport_map = {
  2,
  "thesis_skill_interfaces",
  &_ExecuteSkill_Feedback_message_typesupport_ids.typesupport_identifier[0],
  &_ExecuteSkill_Feedback_message_typesupport_symbol_names.symbol_name[0],
  &_ExecuteSkill_Feedback_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t ExecuteSkill_Feedback_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_ExecuteSkill_Feedback_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_Feedback__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_Feedback__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_Feedback__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace action

}  // namespace thesis_skill_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, thesis_skill_interfaces, action, ExecuteSkill_Feedback)() {
  return &::thesis_skill_interfaces::action::rosidl_typesupport_c::ExecuteSkill_Feedback_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
// already included above
// #include "rosidl_runtime_c/message_type_support_struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__type_support.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
// already included above
// #include "rosidl_typesupport_c/message_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_c/visibility_control.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"

namespace thesis_skill_interfaces
{

namespace action
{

namespace rosidl_typesupport_c
{

typedef struct _ExecuteSkill_SendGoal_Request_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _ExecuteSkill_SendGoal_Request_type_support_ids_t;

static const _ExecuteSkill_SendGoal_Request_type_support_ids_t _ExecuteSkill_SendGoal_Request_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _ExecuteSkill_SendGoal_Request_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _ExecuteSkill_SendGoal_Request_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _ExecuteSkill_SendGoal_Request_type_support_symbol_names_t _ExecuteSkill_SendGoal_Request_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal_Request)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal_Request)),
  }
};

typedef struct _ExecuteSkill_SendGoal_Request_type_support_data_t
{
  void * data[2];
} _ExecuteSkill_SendGoal_Request_type_support_data_t;

static _ExecuteSkill_SendGoal_Request_type_support_data_t _ExecuteSkill_SendGoal_Request_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _ExecuteSkill_SendGoal_Request_message_typesupport_map = {
  2,
  "thesis_skill_interfaces",
  &_ExecuteSkill_SendGoal_Request_message_typesupport_ids.typesupport_identifier[0],
  &_ExecuteSkill_SendGoal_Request_message_typesupport_symbol_names.symbol_name[0],
  &_ExecuteSkill_SendGoal_Request_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t ExecuteSkill_SendGoal_Request_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_ExecuteSkill_SendGoal_Request_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace action

}  // namespace thesis_skill_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal_Request)() {
  return &::thesis_skill_interfaces::action::rosidl_typesupport_c::ExecuteSkill_SendGoal_Request_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
// already included above
// #include "rosidl_runtime_c/message_type_support_struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__type_support.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
// already included above
// #include "rosidl_typesupport_c/message_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_c/visibility_control.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"

namespace thesis_skill_interfaces
{

namespace action
{

namespace rosidl_typesupport_c
{

typedef struct _ExecuteSkill_SendGoal_Response_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _ExecuteSkill_SendGoal_Response_type_support_ids_t;

static const _ExecuteSkill_SendGoal_Response_type_support_ids_t _ExecuteSkill_SendGoal_Response_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _ExecuteSkill_SendGoal_Response_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _ExecuteSkill_SendGoal_Response_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _ExecuteSkill_SendGoal_Response_type_support_symbol_names_t _ExecuteSkill_SendGoal_Response_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal_Response)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal_Response)),
  }
};

typedef struct _ExecuteSkill_SendGoal_Response_type_support_data_t
{
  void * data[2];
} _ExecuteSkill_SendGoal_Response_type_support_data_t;

static _ExecuteSkill_SendGoal_Response_type_support_data_t _ExecuteSkill_SendGoal_Response_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _ExecuteSkill_SendGoal_Response_message_typesupport_map = {
  2,
  "thesis_skill_interfaces",
  &_ExecuteSkill_SendGoal_Response_message_typesupport_ids.typesupport_identifier[0],
  &_ExecuteSkill_SendGoal_Response_message_typesupport_symbol_names.symbol_name[0],
  &_ExecuteSkill_SendGoal_Response_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t ExecuteSkill_SendGoal_Response_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_ExecuteSkill_SendGoal_Response_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace action

}  // namespace thesis_skill_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal_Response)() {
  return &::thesis_skill_interfaces::action::rosidl_typesupport_c::ExecuteSkill_SendGoal_Response_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
// already included above
// #include "rosidl_runtime_c/message_type_support_struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__type_support.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
// already included above
// #include "rosidl_typesupport_c/message_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_c/visibility_control.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"

namespace thesis_skill_interfaces
{

namespace action
{

namespace rosidl_typesupport_c
{

typedef struct _ExecuteSkill_SendGoal_Event_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _ExecuteSkill_SendGoal_Event_type_support_ids_t;

static const _ExecuteSkill_SendGoal_Event_type_support_ids_t _ExecuteSkill_SendGoal_Event_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _ExecuteSkill_SendGoal_Event_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _ExecuteSkill_SendGoal_Event_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _ExecuteSkill_SendGoal_Event_type_support_symbol_names_t _ExecuteSkill_SendGoal_Event_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal_Event)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal_Event)),
  }
};

typedef struct _ExecuteSkill_SendGoal_Event_type_support_data_t
{
  void * data[2];
} _ExecuteSkill_SendGoal_Event_type_support_data_t;

static _ExecuteSkill_SendGoal_Event_type_support_data_t _ExecuteSkill_SendGoal_Event_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _ExecuteSkill_SendGoal_Event_message_typesupport_map = {
  2,
  "thesis_skill_interfaces",
  &_ExecuteSkill_SendGoal_Event_message_typesupport_ids.typesupport_identifier[0],
  &_ExecuteSkill_SendGoal_Event_message_typesupport_symbol_names.symbol_name[0],
  &_ExecuteSkill_SendGoal_Event_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t ExecuteSkill_SendGoal_Event_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_ExecuteSkill_SendGoal_Event_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace action

}  // namespace thesis_skill_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal_Event)() {
  return &::thesis_skill_interfaces::action::rosidl_typesupport_c::ExecuteSkill_SendGoal_Event_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
#include "rosidl_runtime_c/service_type_support_struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__type_support.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
#include "rosidl_typesupport_c/service_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"
#include "service_msgs/msg/service_event_info.h"
#include "builtin_interfaces/msg/time.h"

namespace thesis_skill_interfaces
{

namespace action
{

namespace rosidl_typesupport_c
{
typedef struct _ExecuteSkill_SendGoal_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _ExecuteSkill_SendGoal_type_support_ids_t;

static const _ExecuteSkill_SendGoal_type_support_ids_t _ExecuteSkill_SendGoal_service_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _ExecuteSkill_SendGoal_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _ExecuteSkill_SendGoal_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _ExecuteSkill_SendGoal_type_support_symbol_names_t _ExecuteSkill_SendGoal_service_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_introspection_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal)),
  }
};

typedef struct _ExecuteSkill_SendGoal_type_support_data_t
{
  void * data[2];
} _ExecuteSkill_SendGoal_type_support_data_t;

static _ExecuteSkill_SendGoal_type_support_data_t _ExecuteSkill_SendGoal_service_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _ExecuteSkill_SendGoal_service_typesupport_map = {
  2,
  "thesis_skill_interfaces",
  &_ExecuteSkill_SendGoal_service_typesupport_ids.typesupport_identifier[0],
  &_ExecuteSkill_SendGoal_service_typesupport_symbol_names.symbol_name[0],
  &_ExecuteSkill_SendGoal_service_typesupport_data.data[0],
};

static const rosidl_service_type_support_t ExecuteSkill_SendGoal_service_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_ExecuteSkill_SendGoal_service_typesupport_map),
  rosidl_typesupport_c__get_service_typesupport_handle_function,
  &ExecuteSkill_SendGoal_Request_message_type_support_handle,
  &ExecuteSkill_SendGoal_Response_message_type_support_handle,
  &ExecuteSkill_SendGoal_Event_message_type_support_handle,
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

}  // namespace rosidl_typesupport_c

}  // namespace action

}  // namespace thesis_skill_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_service_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal)() {
  return &::thesis_skill_interfaces::action::rosidl_typesupport_c::ExecuteSkill_SendGoal_service_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
// already included above
// #include "rosidl_runtime_c/message_type_support_struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__type_support.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
// already included above
// #include "rosidl_typesupport_c/message_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_c/visibility_control.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"

namespace thesis_skill_interfaces
{

namespace action
{

namespace rosidl_typesupport_c
{

typedef struct _ExecuteSkill_GetResult_Request_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _ExecuteSkill_GetResult_Request_type_support_ids_t;

static const _ExecuteSkill_GetResult_Request_type_support_ids_t _ExecuteSkill_GetResult_Request_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _ExecuteSkill_GetResult_Request_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _ExecuteSkill_GetResult_Request_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _ExecuteSkill_GetResult_Request_type_support_symbol_names_t _ExecuteSkill_GetResult_Request_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult_Request)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult_Request)),
  }
};

typedef struct _ExecuteSkill_GetResult_Request_type_support_data_t
{
  void * data[2];
} _ExecuteSkill_GetResult_Request_type_support_data_t;

static _ExecuteSkill_GetResult_Request_type_support_data_t _ExecuteSkill_GetResult_Request_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _ExecuteSkill_GetResult_Request_message_typesupport_map = {
  2,
  "thesis_skill_interfaces",
  &_ExecuteSkill_GetResult_Request_message_typesupport_ids.typesupport_identifier[0],
  &_ExecuteSkill_GetResult_Request_message_typesupport_symbol_names.symbol_name[0],
  &_ExecuteSkill_GetResult_Request_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t ExecuteSkill_GetResult_Request_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_ExecuteSkill_GetResult_Request_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace action

}  // namespace thesis_skill_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult_Request)() {
  return &::thesis_skill_interfaces::action::rosidl_typesupport_c::ExecuteSkill_GetResult_Request_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
// already included above
// #include "rosidl_runtime_c/message_type_support_struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__type_support.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
// already included above
// #include "rosidl_typesupport_c/message_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_c/visibility_control.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"

namespace thesis_skill_interfaces
{

namespace action
{

namespace rosidl_typesupport_c
{

typedef struct _ExecuteSkill_GetResult_Response_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _ExecuteSkill_GetResult_Response_type_support_ids_t;

static const _ExecuteSkill_GetResult_Response_type_support_ids_t _ExecuteSkill_GetResult_Response_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _ExecuteSkill_GetResult_Response_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _ExecuteSkill_GetResult_Response_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _ExecuteSkill_GetResult_Response_type_support_symbol_names_t _ExecuteSkill_GetResult_Response_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult_Response)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult_Response)),
  }
};

typedef struct _ExecuteSkill_GetResult_Response_type_support_data_t
{
  void * data[2];
} _ExecuteSkill_GetResult_Response_type_support_data_t;

static _ExecuteSkill_GetResult_Response_type_support_data_t _ExecuteSkill_GetResult_Response_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _ExecuteSkill_GetResult_Response_message_typesupport_map = {
  2,
  "thesis_skill_interfaces",
  &_ExecuteSkill_GetResult_Response_message_typesupport_ids.typesupport_identifier[0],
  &_ExecuteSkill_GetResult_Response_message_typesupport_symbol_names.symbol_name[0],
  &_ExecuteSkill_GetResult_Response_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t ExecuteSkill_GetResult_Response_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_ExecuteSkill_GetResult_Response_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace action

}  // namespace thesis_skill_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult_Response)() {
  return &::thesis_skill_interfaces::action::rosidl_typesupport_c::ExecuteSkill_GetResult_Response_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
// already included above
// #include "rosidl_runtime_c/message_type_support_struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__type_support.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
// already included above
// #include "rosidl_typesupport_c/message_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_c/visibility_control.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"

namespace thesis_skill_interfaces
{

namespace action
{

namespace rosidl_typesupport_c
{

typedef struct _ExecuteSkill_GetResult_Event_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _ExecuteSkill_GetResult_Event_type_support_ids_t;

static const _ExecuteSkill_GetResult_Event_type_support_ids_t _ExecuteSkill_GetResult_Event_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _ExecuteSkill_GetResult_Event_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _ExecuteSkill_GetResult_Event_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _ExecuteSkill_GetResult_Event_type_support_symbol_names_t _ExecuteSkill_GetResult_Event_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult_Event)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult_Event)),
  }
};

typedef struct _ExecuteSkill_GetResult_Event_type_support_data_t
{
  void * data[2];
} _ExecuteSkill_GetResult_Event_type_support_data_t;

static _ExecuteSkill_GetResult_Event_type_support_data_t _ExecuteSkill_GetResult_Event_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _ExecuteSkill_GetResult_Event_message_typesupport_map = {
  2,
  "thesis_skill_interfaces",
  &_ExecuteSkill_GetResult_Event_message_typesupport_ids.typesupport_identifier[0],
  &_ExecuteSkill_GetResult_Event_message_typesupport_symbol_names.symbol_name[0],
  &_ExecuteSkill_GetResult_Event_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t ExecuteSkill_GetResult_Event_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_ExecuteSkill_GetResult_Event_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace action

}  // namespace thesis_skill_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult_Event)() {
  return &::thesis_skill_interfaces::action::rosidl_typesupport_c::ExecuteSkill_GetResult_Event_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
// already included above
// #include "rosidl_runtime_c/service_type_support_struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__type_support.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
// already included above
// #include "rosidl_typesupport_c/service_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"
// already included above
// #include "service_msgs/msg/service_event_info.h"
// already included above
// #include "builtin_interfaces/msg/time.h"

namespace thesis_skill_interfaces
{

namespace action
{

namespace rosidl_typesupport_c
{
typedef struct _ExecuteSkill_GetResult_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _ExecuteSkill_GetResult_type_support_ids_t;

static const _ExecuteSkill_GetResult_type_support_ids_t _ExecuteSkill_GetResult_service_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _ExecuteSkill_GetResult_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _ExecuteSkill_GetResult_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _ExecuteSkill_GetResult_type_support_symbol_names_t _ExecuteSkill_GetResult_service_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_introspection_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult)),
  }
};

typedef struct _ExecuteSkill_GetResult_type_support_data_t
{
  void * data[2];
} _ExecuteSkill_GetResult_type_support_data_t;

static _ExecuteSkill_GetResult_type_support_data_t _ExecuteSkill_GetResult_service_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _ExecuteSkill_GetResult_service_typesupport_map = {
  2,
  "thesis_skill_interfaces",
  &_ExecuteSkill_GetResult_service_typesupport_ids.typesupport_identifier[0],
  &_ExecuteSkill_GetResult_service_typesupport_symbol_names.symbol_name[0],
  &_ExecuteSkill_GetResult_service_typesupport_data.data[0],
};

static const rosidl_service_type_support_t ExecuteSkill_GetResult_service_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_ExecuteSkill_GetResult_service_typesupport_map),
  rosidl_typesupport_c__get_service_typesupport_handle_function,
  &ExecuteSkill_GetResult_Request_message_type_support_handle,
  &ExecuteSkill_GetResult_Response_message_type_support_handle,
  &ExecuteSkill_GetResult_Event_message_type_support_handle,
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

}  // namespace rosidl_typesupport_c

}  // namespace action

}  // namespace thesis_skill_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_service_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult)() {
  return &::thesis_skill_interfaces::action::rosidl_typesupport_c::ExecuteSkill_GetResult_service_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
// already included above
// #include "rosidl_runtime_c/message_type_support_struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__type_support.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
// already included above
// #include "rosidl_typesupport_c/message_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_c/visibility_control.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"

namespace thesis_skill_interfaces
{

namespace action
{

namespace rosidl_typesupport_c
{

typedef struct _ExecuteSkill_FeedbackMessage_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _ExecuteSkill_FeedbackMessage_type_support_ids_t;

static const _ExecuteSkill_FeedbackMessage_type_support_ids_t _ExecuteSkill_FeedbackMessage_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _ExecuteSkill_FeedbackMessage_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _ExecuteSkill_FeedbackMessage_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _ExecuteSkill_FeedbackMessage_type_support_symbol_names_t _ExecuteSkill_FeedbackMessage_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, thesis_skill_interfaces, action, ExecuteSkill_FeedbackMessage)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, thesis_skill_interfaces, action, ExecuteSkill_FeedbackMessage)),
  }
};

typedef struct _ExecuteSkill_FeedbackMessage_type_support_data_t
{
  void * data[2];
} _ExecuteSkill_FeedbackMessage_type_support_data_t;

static _ExecuteSkill_FeedbackMessage_type_support_data_t _ExecuteSkill_FeedbackMessage_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _ExecuteSkill_FeedbackMessage_message_typesupport_map = {
  2,
  "thesis_skill_interfaces",
  &_ExecuteSkill_FeedbackMessage_message_typesupport_ids.typesupport_identifier[0],
  &_ExecuteSkill_FeedbackMessage_message_typesupport_symbol_names.symbol_name[0],
  &_ExecuteSkill_FeedbackMessage_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t ExecuteSkill_FeedbackMessage_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_ExecuteSkill_FeedbackMessage_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace action

}  // namespace thesis_skill_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, thesis_skill_interfaces, action, ExecuteSkill_FeedbackMessage)() {
  return &::thesis_skill_interfaces::action::rosidl_typesupport_c::ExecuteSkill_FeedbackMessage_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif

#include "action_msgs/msg/goal_status_array.h"
#include "action_msgs/srv/cancel_goal.h"
#include "thesis_skill_interfaces/action/execute_skill.h"
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__type_support.h"

static rosidl_action_type_support_t _thesis_skill_interfaces__action__ExecuteSkill__typesupport_c = {
  NULL, NULL, NULL, NULL, NULL,
  &thesis_skill_interfaces__action__ExecuteSkill__get_type_hash,
  &thesis_skill_interfaces__action__ExecuteSkill__get_type_description,
  &thesis_skill_interfaces__action__ExecuteSkill__get_type_description_sources,
};

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_action_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__ACTION_SYMBOL_NAME(
  rosidl_typesupport_c, thesis_skill_interfaces, action, ExecuteSkill)()
{
  // Thread-safe by always writing the same values to the static struct
  _thesis_skill_interfaces__action__ExecuteSkill__typesupport_c.goal_service_type_support =
    ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(
    rosidl_typesupport_c, thesis_skill_interfaces, action, ExecuteSkill_SendGoal)();
  _thesis_skill_interfaces__action__ExecuteSkill__typesupport_c.result_service_type_support =
    ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(
    rosidl_typesupport_c, thesis_skill_interfaces, action, ExecuteSkill_GetResult)();
  _thesis_skill_interfaces__action__ExecuteSkill__typesupport_c.cancel_service_type_support =
    ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(
    rosidl_typesupport_c, action_msgs, srv, CancelGoal)();
  _thesis_skill_interfaces__action__ExecuteSkill__typesupport_c.feedback_message_type_support =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(
    rosidl_typesupport_c, thesis_skill_interfaces, action, ExecuteSkill_FeedbackMessage)();
  _thesis_skill_interfaces__action__ExecuteSkill__typesupport_c.status_message_type_support =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(
    rosidl_typesupport_c, action_msgs, msg, GoalStatusArray)();

  return &_thesis_skill_interfaces__action__ExecuteSkill__typesupport_c;
}

#ifdef __cplusplus
}
#endif
