// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from thesis_skill_interfaces:action/ExecuteSkill.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "thesis_skill_interfaces/action/execute_skill.h"


#ifndef THESIS_SKILL_INTERFACES__ACTION__DETAIL__EXECUTE_SKILL__STRUCT_H_
#define THESIS_SKILL_INTERFACES__ACTION__DETAIL__EXECUTE_SKILL__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


// Constants defined in the message

// Include directives for member types
// Member 'skill_id'
// Member 'skill_version'
// Member 'request_id'
// Member 'parameters_json'
#include "rosidl_runtime_c/string.h"

/// Struct defined in action/ExecuteSkill in the package thesis_skill_interfaces.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_Goal
{
  rosidl_runtime_c__String skill_id;
  rosidl_runtime_c__String skill_version;
  rosidl_runtime_c__String request_id;
  rosidl_runtime_c__String parameters_json;
} thesis_skill_interfaces__action__ExecuteSkill_Goal;

// Struct for a sequence of thesis_skill_interfaces__action__ExecuteSkill_Goal.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence
{
  thesis_skill_interfaces__action__ExecuteSkill_Goal * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'execution_status'
// Member 'runtime_check'
// Member 'reason'
// Member 'evidence_id'
// already included above
// #include "rosidl_runtime_c/string.h"

/// Struct defined in action/ExecuteSkill in the package thesis_skill_interfaces.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_Result
{
  rosidl_runtime_c__String execution_status;
  rosidl_runtime_c__String runtime_check;
  rosidl_runtime_c__String reason;
  rosidl_runtime_c__String evidence_id;
} thesis_skill_interfaces__action__ExecuteSkill_Result;

// Struct for a sequence of thesis_skill_interfaces__action__ExecuteSkill_Result.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence
{
  thesis_skill_interfaces__action__ExecuteSkill_Result * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'stage'
// Member 'event'
// already included above
// #include "rosidl_runtime_c/string.h"

/// Struct defined in action/ExecuteSkill in the package thesis_skill_interfaces.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_Feedback
{
  rosidl_runtime_c__String stage;
  rosidl_runtime_c__String event;
  double simulation_seconds;
} thesis_skill_interfaces__action__ExecuteSkill_Feedback;

// Struct for a sequence of thesis_skill_interfaces__action__ExecuteSkill_Feedback.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence
{
  thesis_skill_interfaces__action__ExecuteSkill_Feedback * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'goal_id'
#include "unique_identifier_msgs/msg/detail/uuid__struct.h"
// Member 'goal'
#include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"

/// Struct defined in action/ExecuteSkill in the package thesis_skill_interfaces.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request
{
  unique_identifier_msgs__msg__UUID goal_id;
  thesis_skill_interfaces__action__ExecuteSkill_Goal goal;
} thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request;

// Struct for a sequence of thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence
{
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'stamp'
#include "builtin_interfaces/msg/detail/time__struct.h"

/// Struct defined in action/ExecuteSkill in the package thesis_skill_interfaces.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response
{
  bool accepted;
  builtin_interfaces__msg__Time stamp;
} thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response;

// Struct for a sequence of thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence
{
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'info'
#include "service_msgs/msg/detail/service_event_info__struct.h"

// constants for array fields with an upper bound
// request
enum
{
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__request__MAX_SIZE = 1
};
// response
enum
{
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__response__MAX_SIZE = 1
};

/// Struct defined in action/ExecuteSkill in the package thesis_skill_interfaces.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event
{
  service_msgs__msg__ServiceEventInfo info;
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence request;
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence response;
} thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event;

// Struct for a sequence of thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence
{
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'goal_id'
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__struct.h"

/// Struct defined in action/ExecuteSkill in the package thesis_skill_interfaces.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request
{
  unique_identifier_msgs__msg__UUID goal_id;
} thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request;

// Struct for a sequence of thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence
{
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'result'
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"

/// Struct defined in action/ExecuteSkill in the package thesis_skill_interfaces.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response
{
  int8_t status;
  thesis_skill_interfaces__action__ExecuteSkill_Result result;
} thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response;

// Struct for a sequence of thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence
{
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'info'
// already included above
// #include "service_msgs/msg/detail/service_event_info__struct.h"

// constants for array fields with an upper bound
// request
enum
{
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__request__MAX_SIZE = 1
};
// response
enum
{
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__response__MAX_SIZE = 1
};

/// Struct defined in action/ExecuteSkill in the package thesis_skill_interfaces.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event
{
  service_msgs__msg__ServiceEventInfo info;
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence request;
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence response;
} thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event;

// Struct for a sequence of thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence
{
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'goal_id'
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__struct.h"
// Member 'feedback'
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__struct.h"

/// Struct defined in action/ExecuteSkill in the package thesis_skill_interfaces.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage
{
  unique_identifier_msgs__msg__UUID goal_id;
  thesis_skill_interfaces__action__ExecuteSkill_Feedback feedback;
} thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage;

// Struct for a sequence of thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage.
typedef struct thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence
{
  thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // THESIS_SKILL_INTERFACES__ACTION__DETAIL__EXECUTE_SKILL__STRUCT_H_
