// generated from rosidl_generator_c/resource/idl__functions.c.em
// with input from thesis_skill_interfaces:action/ExecuteSkill.idl
// generated code does not contain a copyright notice
#include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"

#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "rcutils/allocator.h"


// Include directives for member types
// Member `skill_id`
// Member `skill_version`
// Member `request_id`
// Member `parameters_json`
#include "rosidl_runtime_c/string_functions.h"

bool
thesis_skill_interfaces__action__ExecuteSkill_Goal__init(thesis_skill_interfaces__action__ExecuteSkill_Goal * msg)
{
  if (!msg) {
    return false;
  }
  // skill_id
  if (!rosidl_runtime_c__String__init(&msg->skill_id)) {
    thesis_skill_interfaces__action__ExecuteSkill_Goal__fini(msg);
    return false;
  }
  // skill_version
  if (!rosidl_runtime_c__String__init(&msg->skill_version)) {
    thesis_skill_interfaces__action__ExecuteSkill_Goal__fini(msg);
    return false;
  }
  // request_id
  if (!rosidl_runtime_c__String__init(&msg->request_id)) {
    thesis_skill_interfaces__action__ExecuteSkill_Goal__fini(msg);
    return false;
  }
  // parameters_json
  if (!rosidl_runtime_c__String__init(&msg->parameters_json)) {
    thesis_skill_interfaces__action__ExecuteSkill_Goal__fini(msg);
    return false;
  }
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_Goal__fini(thesis_skill_interfaces__action__ExecuteSkill_Goal * msg)
{
  if (!msg) {
    return;
  }
  // skill_id
  rosidl_runtime_c__String__fini(&msg->skill_id);
  // skill_version
  rosidl_runtime_c__String__fini(&msg->skill_version);
  // request_id
  rosidl_runtime_c__String__fini(&msg->request_id);
  // parameters_json
  rosidl_runtime_c__String__fini(&msg->parameters_json);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_Goal__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_Goal * lhs, const thesis_skill_interfaces__action__ExecuteSkill_Goal * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // skill_id
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->skill_id), &(rhs->skill_id)))
  {
    return false;
  }
  // skill_version
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->skill_version), &(rhs->skill_version)))
  {
    return false;
  }
  // request_id
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->request_id), &(rhs->request_id)))
  {
    return false;
  }
  // parameters_json
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->parameters_json), &(rhs->parameters_json)))
  {
    return false;
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_Goal__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_Goal * input,
  thesis_skill_interfaces__action__ExecuteSkill_Goal * output)
{
  if (!input || !output) {
    return false;
  }
  // skill_id
  if (!rosidl_runtime_c__String__copy(
      &(input->skill_id), &(output->skill_id)))
  {
    return false;
  }
  // skill_version
  if (!rosidl_runtime_c__String__copy(
      &(input->skill_version), &(output->skill_version)))
  {
    return false;
  }
  // request_id
  if (!rosidl_runtime_c__String__copy(
      &(input->request_id), &(output->request_id)))
  {
    return false;
  }
  // parameters_json
  if (!rosidl_runtime_c__String__copy(
      &(input->parameters_json), &(output->parameters_json)))
  {
    return false;
  }
  return true;
}

thesis_skill_interfaces__action__ExecuteSkill_Goal *
thesis_skill_interfaces__action__ExecuteSkill_Goal__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_Goal * msg = (thesis_skill_interfaces__action__ExecuteSkill_Goal *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_Goal), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(thesis_skill_interfaces__action__ExecuteSkill_Goal));
  bool success = thesis_skill_interfaces__action__ExecuteSkill_Goal__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
thesis_skill_interfaces__action__ExecuteSkill_Goal__destroy(thesis_skill_interfaces__action__ExecuteSkill_Goal * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    thesis_skill_interfaces__action__ExecuteSkill_Goal__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence__init(thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_Goal * data = NULL;

  if (size) {
    if (size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_Goal)) {
      return false;
    }
    data = (thesis_skill_interfaces__action__ExecuteSkill_Goal *)allocator.zero_allocate(size, sizeof(thesis_skill_interfaces__action__ExecuteSkill_Goal), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = thesis_skill_interfaces__action__ExecuteSkill_Goal__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        thesis_skill_interfaces__action__ExecuteSkill_Goal__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence__fini(thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      thesis_skill_interfaces__action__ExecuteSkill_Goal__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence *
thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence * array = (thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence__destroy(thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence * lhs, const thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_Goal__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence * input,
  thesis_skill_interfaces__action__ExecuteSkill_Goal__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    if (input->size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_Goal)) {
      return false;
    }
    const size_t allocation_size =
      input->size * sizeof(thesis_skill_interfaces__action__ExecuteSkill_Goal);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    thesis_skill_interfaces__action__ExecuteSkill_Goal * data =
      (thesis_skill_interfaces__action__ExecuteSkill_Goal *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!thesis_skill_interfaces__action__ExecuteSkill_Goal__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          thesis_skill_interfaces__action__ExecuteSkill_Goal__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_Goal__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `execution_status`
// Member `runtime_check`
// Member `reason`
// Member `evidence_id`
// already included above
// #include "rosidl_runtime_c/string_functions.h"

bool
thesis_skill_interfaces__action__ExecuteSkill_Result__init(thesis_skill_interfaces__action__ExecuteSkill_Result * msg)
{
  if (!msg) {
    return false;
  }
  // execution_status
  if (!rosidl_runtime_c__String__init(&msg->execution_status)) {
    thesis_skill_interfaces__action__ExecuteSkill_Result__fini(msg);
    return false;
  }
  // runtime_check
  if (!rosidl_runtime_c__String__init(&msg->runtime_check)) {
    thesis_skill_interfaces__action__ExecuteSkill_Result__fini(msg);
    return false;
  }
  // reason
  if (!rosidl_runtime_c__String__init(&msg->reason)) {
    thesis_skill_interfaces__action__ExecuteSkill_Result__fini(msg);
    return false;
  }
  // evidence_id
  if (!rosidl_runtime_c__String__init(&msg->evidence_id)) {
    thesis_skill_interfaces__action__ExecuteSkill_Result__fini(msg);
    return false;
  }
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_Result__fini(thesis_skill_interfaces__action__ExecuteSkill_Result * msg)
{
  if (!msg) {
    return;
  }
  // execution_status
  rosidl_runtime_c__String__fini(&msg->execution_status);
  // runtime_check
  rosidl_runtime_c__String__fini(&msg->runtime_check);
  // reason
  rosidl_runtime_c__String__fini(&msg->reason);
  // evidence_id
  rosidl_runtime_c__String__fini(&msg->evidence_id);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_Result__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_Result * lhs, const thesis_skill_interfaces__action__ExecuteSkill_Result * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // execution_status
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->execution_status), &(rhs->execution_status)))
  {
    return false;
  }
  // runtime_check
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->runtime_check), &(rhs->runtime_check)))
  {
    return false;
  }
  // reason
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->reason), &(rhs->reason)))
  {
    return false;
  }
  // evidence_id
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->evidence_id), &(rhs->evidence_id)))
  {
    return false;
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_Result__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_Result * input,
  thesis_skill_interfaces__action__ExecuteSkill_Result * output)
{
  if (!input || !output) {
    return false;
  }
  // execution_status
  if (!rosidl_runtime_c__String__copy(
      &(input->execution_status), &(output->execution_status)))
  {
    return false;
  }
  // runtime_check
  if (!rosidl_runtime_c__String__copy(
      &(input->runtime_check), &(output->runtime_check)))
  {
    return false;
  }
  // reason
  if (!rosidl_runtime_c__String__copy(
      &(input->reason), &(output->reason)))
  {
    return false;
  }
  // evidence_id
  if (!rosidl_runtime_c__String__copy(
      &(input->evidence_id), &(output->evidence_id)))
  {
    return false;
  }
  return true;
}

thesis_skill_interfaces__action__ExecuteSkill_Result *
thesis_skill_interfaces__action__ExecuteSkill_Result__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_Result * msg = (thesis_skill_interfaces__action__ExecuteSkill_Result *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_Result), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(thesis_skill_interfaces__action__ExecuteSkill_Result));
  bool success = thesis_skill_interfaces__action__ExecuteSkill_Result__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
thesis_skill_interfaces__action__ExecuteSkill_Result__destroy(thesis_skill_interfaces__action__ExecuteSkill_Result * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    thesis_skill_interfaces__action__ExecuteSkill_Result__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence__init(thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_Result * data = NULL;

  if (size) {
    if (size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_Result)) {
      return false;
    }
    data = (thesis_skill_interfaces__action__ExecuteSkill_Result *)allocator.zero_allocate(size, sizeof(thesis_skill_interfaces__action__ExecuteSkill_Result), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = thesis_skill_interfaces__action__ExecuteSkill_Result__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        thesis_skill_interfaces__action__ExecuteSkill_Result__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence__fini(thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      thesis_skill_interfaces__action__ExecuteSkill_Result__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence *
thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence * array = (thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence__destroy(thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence * lhs, const thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_Result__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence * input,
  thesis_skill_interfaces__action__ExecuteSkill_Result__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    if (input->size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_Result)) {
      return false;
    }
    const size_t allocation_size =
      input->size * sizeof(thesis_skill_interfaces__action__ExecuteSkill_Result);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    thesis_skill_interfaces__action__ExecuteSkill_Result * data =
      (thesis_skill_interfaces__action__ExecuteSkill_Result *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!thesis_skill_interfaces__action__ExecuteSkill_Result__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          thesis_skill_interfaces__action__ExecuteSkill_Result__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_Result__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `stage`
// Member `event`
// already included above
// #include "rosidl_runtime_c/string_functions.h"

bool
thesis_skill_interfaces__action__ExecuteSkill_Feedback__init(thesis_skill_interfaces__action__ExecuteSkill_Feedback * msg)
{
  if (!msg) {
    return false;
  }
  // stage
  if (!rosidl_runtime_c__String__init(&msg->stage)) {
    thesis_skill_interfaces__action__ExecuteSkill_Feedback__fini(msg);
    return false;
  }
  // event
  if (!rosidl_runtime_c__String__init(&msg->event)) {
    thesis_skill_interfaces__action__ExecuteSkill_Feedback__fini(msg);
    return false;
  }
  // simulation_seconds
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_Feedback__fini(thesis_skill_interfaces__action__ExecuteSkill_Feedback * msg)
{
  if (!msg) {
    return;
  }
  // stage
  rosidl_runtime_c__String__fini(&msg->stage);
  // event
  rosidl_runtime_c__String__fini(&msg->event);
  // simulation_seconds
}

bool
thesis_skill_interfaces__action__ExecuteSkill_Feedback__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_Feedback * lhs, const thesis_skill_interfaces__action__ExecuteSkill_Feedback * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // stage
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->stage), &(rhs->stage)))
  {
    return false;
  }
  // event
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->event), &(rhs->event)))
  {
    return false;
  }
  // simulation_seconds
  if (lhs->simulation_seconds != rhs->simulation_seconds) {
    return false;
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_Feedback__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_Feedback * input,
  thesis_skill_interfaces__action__ExecuteSkill_Feedback * output)
{
  if (!input || !output) {
    return false;
  }
  // stage
  if (!rosidl_runtime_c__String__copy(
      &(input->stage), &(output->stage)))
  {
    return false;
  }
  // event
  if (!rosidl_runtime_c__String__copy(
      &(input->event), &(output->event)))
  {
    return false;
  }
  // simulation_seconds
  output->simulation_seconds = input->simulation_seconds;
  return true;
}

thesis_skill_interfaces__action__ExecuteSkill_Feedback *
thesis_skill_interfaces__action__ExecuteSkill_Feedback__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_Feedback * msg = (thesis_skill_interfaces__action__ExecuteSkill_Feedback *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_Feedback), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(thesis_skill_interfaces__action__ExecuteSkill_Feedback));
  bool success = thesis_skill_interfaces__action__ExecuteSkill_Feedback__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
thesis_skill_interfaces__action__ExecuteSkill_Feedback__destroy(thesis_skill_interfaces__action__ExecuteSkill_Feedback * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    thesis_skill_interfaces__action__ExecuteSkill_Feedback__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence__init(thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_Feedback * data = NULL;

  if (size) {
    if (size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_Feedback)) {
      return false;
    }
    data = (thesis_skill_interfaces__action__ExecuteSkill_Feedback *)allocator.zero_allocate(size, sizeof(thesis_skill_interfaces__action__ExecuteSkill_Feedback), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = thesis_skill_interfaces__action__ExecuteSkill_Feedback__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        thesis_skill_interfaces__action__ExecuteSkill_Feedback__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence__fini(thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      thesis_skill_interfaces__action__ExecuteSkill_Feedback__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence *
thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence * array = (thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence__destroy(thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence * lhs, const thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_Feedback__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence * input,
  thesis_skill_interfaces__action__ExecuteSkill_Feedback__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    if (input->size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_Feedback)) {
      return false;
    }
    const size_t allocation_size =
      input->size * sizeof(thesis_skill_interfaces__action__ExecuteSkill_Feedback);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    thesis_skill_interfaces__action__ExecuteSkill_Feedback * data =
      (thesis_skill_interfaces__action__ExecuteSkill_Feedback *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!thesis_skill_interfaces__action__ExecuteSkill_Feedback__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          thesis_skill_interfaces__action__ExecuteSkill_Feedback__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_Feedback__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `goal_id`
#include "unique_identifier_msgs/msg/detail/uuid__functions.h"
// Member `goal`
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"

bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__init(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * msg)
{
  if (!msg) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__init(&msg->goal_id)) {
    thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__fini(msg);
    return false;
  }
  // goal
  if (!thesis_skill_interfaces__action__ExecuteSkill_Goal__init(&msg->goal)) {
    thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__fini(msg);
    return false;
  }
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__fini(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * msg)
{
  if (!msg) {
    return;
  }
  // goal_id
  unique_identifier_msgs__msg__UUID__fini(&msg->goal_id);
  // goal
  thesis_skill_interfaces__action__ExecuteSkill_Goal__fini(&msg->goal);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * lhs, const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__are_equal(
      &(lhs->goal_id), &(rhs->goal_id)))
  {
    return false;
  }
  // goal
  if (!thesis_skill_interfaces__action__ExecuteSkill_Goal__are_equal(
      &(lhs->goal), &(rhs->goal)))
  {
    return false;
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * input,
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * output)
{
  if (!input || !output) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__copy(
      &(input->goal_id), &(output->goal_id)))
  {
    return false;
  }
  // goal
  if (!thesis_skill_interfaces__action__ExecuteSkill_Goal__copy(
      &(input->goal), &(output->goal)))
  {
    return false;
  }
  return true;
}

thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request *
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * msg = (thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request));
  bool success = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__destroy(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence__init(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * data = NULL;

  if (size) {
    if (size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request)) {
      return false;
    }
    data = (thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request *)allocator.zero_allocate(size, sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence__fini(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence *
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence * array = (thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence__destroy(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence * lhs, const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence * input,
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    if (input->size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request)) {
      return false;
    }
    const size_t allocation_size =
      input->size * sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request * data =
      (thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `stamp`
#include "builtin_interfaces/msg/detail/time__functions.h"

bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__init(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * msg)
{
  if (!msg) {
    return false;
  }
  // accepted
  // stamp
  if (!builtin_interfaces__msg__Time__init(&msg->stamp)) {
    thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__fini(msg);
    return false;
  }
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__fini(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * msg)
{
  if (!msg) {
    return;
  }
  // accepted
  // stamp
  builtin_interfaces__msg__Time__fini(&msg->stamp);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * lhs, const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // accepted
  if (lhs->accepted != rhs->accepted) {
    return false;
  }
  // stamp
  if (!builtin_interfaces__msg__Time__are_equal(
      &(lhs->stamp), &(rhs->stamp)))
  {
    return false;
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * input,
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * output)
{
  if (!input || !output) {
    return false;
  }
  // accepted
  output->accepted = input->accepted;
  // stamp
  if (!builtin_interfaces__msg__Time__copy(
      &(input->stamp), &(output->stamp)))
  {
    return false;
  }
  return true;
}

thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response *
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * msg = (thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response));
  bool success = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__destroy(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence__init(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * data = NULL;

  if (size) {
    if (size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response)) {
      return false;
    }
    data = (thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response *)allocator.zero_allocate(size, sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence__fini(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence *
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence * array = (thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence__destroy(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence * lhs, const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence * input,
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    if (input->size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response)) {
      return false;
    }
    const size_t allocation_size =
      input->size * sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response * data =
      (thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `info`
#include "service_msgs/msg/detail/service_event_info__functions.h"
// Member `request`
// Member `response`
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"

bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__init(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event * msg)
{
  if (!msg) {
    return false;
  }
  // info
  if (!service_msgs__msg__ServiceEventInfo__init(&msg->info)) {
    thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__fini(msg);
    return false;
  }
  // request
  if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence__init(&msg->request, 0)) {
    thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__fini(msg);
    return false;
  }
  // response
  if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence__init(&msg->response, 0)) {
    thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__fini(msg);
    return false;
  }
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__fini(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event * msg)
{
  if (!msg) {
    return;
  }
  // info
  service_msgs__msg__ServiceEventInfo__fini(&msg->info);
  // request
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence__fini(&msg->request);
  // response
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence__fini(&msg->response);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event * lhs, const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // info
  if (!service_msgs__msg__ServiceEventInfo__are_equal(
      &(lhs->info), &(rhs->info)))
  {
    return false;
  }
  // request
  if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence__are_equal(
      &(lhs->request), &(rhs->request)))
  {
    return false;
  }
  // response
  if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence__are_equal(
      &(lhs->response), &(rhs->response)))
  {
    return false;
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event * input,
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event * output)
{
  if (!input || !output) {
    return false;
  }
  // info
  if (!service_msgs__msg__ServiceEventInfo__copy(
      &(input->info), &(output->info)))
  {
    return false;
  }
  // request
  if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Request__Sequence__copy(
      &(input->request), &(output->request)))
  {
    return false;
  }
  // response
  if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Response__Sequence__copy(
      &(input->response), &(output->response)))
  {
    return false;
  }
  return true;
}

thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event *
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event * msg = (thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event));
  bool success = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__destroy(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence__init(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event * data = NULL;

  if (size) {
    if (size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event)) {
      return false;
    }
    data = (thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event *)allocator.zero_allocate(size, sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence__fini(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence *
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence * array = (thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence__destroy(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence * lhs, const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence * input,
  thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    if (input->size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event)) {
      return false;
    }
    const size_t allocation_size =
      input->size * sizeof(thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event * data =
      (thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_SendGoal_Event__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `goal_id`
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__functions.h"

bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__init(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * msg)
{
  if (!msg) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__init(&msg->goal_id)) {
    thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__fini(msg);
    return false;
  }
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__fini(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * msg)
{
  if (!msg) {
    return;
  }
  // goal_id
  unique_identifier_msgs__msg__UUID__fini(&msg->goal_id);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * lhs, const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__are_equal(
      &(lhs->goal_id), &(rhs->goal_id)))
  {
    return false;
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * input,
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * output)
{
  if (!input || !output) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__copy(
      &(input->goal_id), &(output->goal_id)))
  {
    return false;
  }
  return true;
}

thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request *
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * msg = (thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request));
  bool success = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__destroy(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence__init(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * data = NULL;

  if (size) {
    if (size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request)) {
      return false;
    }
    data = (thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request *)allocator.zero_allocate(size, sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence__fini(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence *
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence * array = (thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence__destroy(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence * lhs, const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence * input,
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    if (input->size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request)) {
      return false;
    }
    const size_t allocation_size =
      input->size * sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request * data =
      (thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `result`
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"

bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__init(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * msg)
{
  if (!msg) {
    return false;
  }
  // status
  // result
  if (!thesis_skill_interfaces__action__ExecuteSkill_Result__init(&msg->result)) {
    thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__fini(msg);
    return false;
  }
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__fini(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * msg)
{
  if (!msg) {
    return;
  }
  // status
  // result
  thesis_skill_interfaces__action__ExecuteSkill_Result__fini(&msg->result);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * lhs, const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // status
  if (lhs->status != rhs->status) {
    return false;
  }
  // result
  if (!thesis_skill_interfaces__action__ExecuteSkill_Result__are_equal(
      &(lhs->result), &(rhs->result)))
  {
    return false;
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * input,
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * output)
{
  if (!input || !output) {
    return false;
  }
  // status
  output->status = input->status;
  // result
  if (!thesis_skill_interfaces__action__ExecuteSkill_Result__copy(
      &(input->result), &(output->result)))
  {
    return false;
  }
  return true;
}

thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response *
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * msg = (thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response));
  bool success = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__destroy(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence__init(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * data = NULL;

  if (size) {
    if (size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response)) {
      return false;
    }
    data = (thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response *)allocator.zero_allocate(size, sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence__fini(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence *
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence * array = (thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence__destroy(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence * lhs, const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence * input,
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    if (input->size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response)) {
      return false;
    }
    const size_t allocation_size =
      input->size * sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response * data =
      (thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `info`
// already included above
// #include "service_msgs/msg/detail/service_event_info__functions.h"
// Member `request`
// Member `response`
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"

bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__init(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event * msg)
{
  if (!msg) {
    return false;
  }
  // info
  if (!service_msgs__msg__ServiceEventInfo__init(&msg->info)) {
    thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__fini(msg);
    return false;
  }
  // request
  if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence__init(&msg->request, 0)) {
    thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__fini(msg);
    return false;
  }
  // response
  if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence__init(&msg->response, 0)) {
    thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__fini(msg);
    return false;
  }
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__fini(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event * msg)
{
  if (!msg) {
    return;
  }
  // info
  service_msgs__msg__ServiceEventInfo__fini(&msg->info);
  // request
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence__fini(&msg->request);
  // response
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence__fini(&msg->response);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event * lhs, const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // info
  if (!service_msgs__msg__ServiceEventInfo__are_equal(
      &(lhs->info), &(rhs->info)))
  {
    return false;
  }
  // request
  if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence__are_equal(
      &(lhs->request), &(rhs->request)))
  {
    return false;
  }
  // response
  if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence__are_equal(
      &(lhs->response), &(rhs->response)))
  {
    return false;
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event * input,
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event * output)
{
  if (!input || !output) {
    return false;
  }
  // info
  if (!service_msgs__msg__ServiceEventInfo__copy(
      &(input->info), &(output->info)))
  {
    return false;
  }
  // request
  if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Request__Sequence__copy(
      &(input->request), &(output->request)))
  {
    return false;
  }
  // response
  if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Response__Sequence__copy(
      &(input->response), &(output->response)))
  {
    return false;
  }
  return true;
}

thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event *
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event * msg = (thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event));
  bool success = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__destroy(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence__init(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event * data = NULL;

  if (size) {
    if (size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event)) {
      return false;
    }
    data = (thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event *)allocator.zero_allocate(size, sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence__fini(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence *
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence * array = (thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence__destroy(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence * lhs, const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence * input,
  thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    if (input->size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event)) {
      return false;
    }
    const size_t allocation_size =
      input->size * sizeof(thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event * data =
      (thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_GetResult_Event__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `goal_id`
// already included above
// #include "unique_identifier_msgs/msg/detail/uuid__functions.h"
// Member `feedback`
// already included above
// #include "thesis_skill_interfaces/action/detail/execute_skill__functions.h"

bool
thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__init(thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage * msg)
{
  if (!msg) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__init(&msg->goal_id)) {
    thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__fini(msg);
    return false;
  }
  // feedback
  if (!thesis_skill_interfaces__action__ExecuteSkill_Feedback__init(&msg->feedback)) {
    thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__fini(msg);
    return false;
  }
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__fini(thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage * msg)
{
  if (!msg) {
    return;
  }
  // goal_id
  unique_identifier_msgs__msg__UUID__fini(&msg->goal_id);
  // feedback
  thesis_skill_interfaces__action__ExecuteSkill_Feedback__fini(&msg->feedback);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage * lhs, const thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__are_equal(
      &(lhs->goal_id), &(rhs->goal_id)))
  {
    return false;
  }
  // feedback
  if (!thesis_skill_interfaces__action__ExecuteSkill_Feedback__are_equal(
      &(lhs->feedback), &(rhs->feedback)))
  {
    return false;
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage * input,
  thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage * output)
{
  if (!input || !output) {
    return false;
  }
  // goal_id
  if (!unique_identifier_msgs__msg__UUID__copy(
      &(input->goal_id), &(output->goal_id)))
  {
    return false;
  }
  // feedback
  if (!thesis_skill_interfaces__action__ExecuteSkill_Feedback__copy(
      &(input->feedback), &(output->feedback)))
  {
    return false;
  }
  return true;
}

thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage *
thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage * msg = (thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage));
  bool success = thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__destroy(thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence__init(thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage * data = NULL;

  if (size) {
    if (size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage)) {
      return false;
    }
    data = (thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage *)allocator.zero_allocate(size, sizeof(thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence__fini(thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence *
thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence * array = (thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence *)allocator.allocate(sizeof(thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence__destroy(thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence__are_equal(const thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence * lhs, const thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence__copy(
  const thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence * input,
  thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    if (input->size > SIZE_MAX / sizeof(thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage)) {
      return false;
    }
    const size_t allocation_size =
      input->size * sizeof(thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage * data =
      (thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!thesis_skill_interfaces__action__ExecuteSkill_FeedbackMessage__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}
