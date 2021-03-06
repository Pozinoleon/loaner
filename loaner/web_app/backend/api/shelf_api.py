# Copyright 2018 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The entry point for the Shelf methods."""

import logging

from protorpc import message_types

from google.appengine.api import datastore_errors

import endpoints

from loaner.web_app.backend.api import loaner_endpoints
from loaner.web_app.backend.api import root_api
from loaner.web_app.backend.api.messages import shelf_message
from loaner.web_app.backend.lib import user
from loaner.web_app.backend.models import device_model
from loaner.web_app.backend.models import shelf_model

_SHELF_DOES_NOT_EXIST_MSG = (
    'The shelf with location: %s does not exist. Please double '
    'check the location.')
_DEVICE_DOES_NOT_EXIST_MSG = (
    'The device_identifier: %s is either not enrolled or an invalid serial '
    'number has been entered.')



@root_api.ROOT_API.api_class(resource_name='shelf', path='shelf')
class ShelfApi(root_api.Service):
  """This class is for the Shelf API."""

  @loaner_endpoints.authed_method(
      shelf_message.EnrollShelfRequest,
      message_types.VoidMessage,
      name='enroll',
      path='enroll',
      http_method='POST',
      permission='enroll_shelf')
  def enroll(self, request):
    """Enroll request for the Shelf API."""
    user_email = user.get_user_email()
    self.check_xsrf_token(self.request_state)
    try:
      shelf_model.Shelf.enroll(
          user_email=user_email,
          friendly_name=request.friendly_name,
          location=request.location,
          latitude=request.latitude,
          longitude=request.longitude,
          altitude=request.altitude,
          capacity=request.capacity,
          audit_notification_enabled=request.audit_notification_enabled,
          responsible_for_audit=request.responsible_for_audit)
    except (shelf_model.EnrollmentError, datastore_errors.BadValueError) as err:
      raise endpoints.BadRequestException(str(err))

    return message_types.VoidMessage()

  @loaner_endpoints.authed_method(
      shelf_message.GetShelfRequest,
      shelf_message.Shelf,
      name='get',
      path='get',
      http_method='POST',
      permission='get_shelf')
  def get(self, request):
    """Get a shelf based on location."""
    self.check_xsrf_token(self.request_state)
    shelf = get_shelf(location=request.location)
    shelf_dict = self.to_dict(shelf, shelf_model.Shelf)

    return shelf_message.Shelf(
        location=shelf_dict.get('location'),
        capacity=shelf_dict.get('capacity'),
        friendly_name=shelf_dict.get('friendly_name'),
        latitude=shelf_dict.get('lat_long.lat'),
        longitude=shelf_dict.get('lat_long.lon'),
        altitude=shelf_dict.get('altitude'),
        audit_requested=shelf_dict.get('audit_requested'),
        responsible_for_audit=shelf_dict.get('responsible_for_audit'),
        last_audit_time=shelf_dict.get('last_audit_time'),
        last_audit_by=shelf_dict.get('last_audit_by'),
        enabled=shelf_dict.get('enabled'))

  @loaner_endpoints.authed_method(
      shelf_message.GetShelfRequest,
      message_types.VoidMessage,
      name='disable',
      path='disable',
      http_method='POST',
      permission='disable_shelf')
  def disable(self, request):
    """Disable a shelf by its location."""
    self.check_xsrf_token(self.request_state)
    user_email = user.get_user_email()
    shelf = get_shelf(location=request.location)
    shelf.disable(user_email)

    return message_types.VoidMessage()

  @loaner_endpoints.authed_method(
      shelf_message.GetShelfRequest,
      message_types.VoidMessage,
      name='enable',
      path='enable',
      http_method='POST',
      permission='enable_shelf')
  def enable(self, request):
    """Enable a shelf based on its location."""
    self.check_xsrf_token(self.request_state)
    user_email = user.get_user_email()
    shelf = get_shelf(location=request.location)
    shelf.enable(user_email)

    return message_types.VoidMessage()

  @loaner_endpoints.authed_method(
      shelf_message.UpdateShelfRequest,
      message_types.VoidMessage,
      name='update',
      path='update',
      http_method='POST',
      permission='update_shelf')
  def update(self, request):
    """Get a shelf using location to update its properties."""
    self.check_xsrf_token(self.request_state)
    user_email = user.get_user_email()
    shelf = get_shelf(location=request.current_location)
    kwargs = self.to_dict(request, shelf_model.Shelf)
    shelf.edit(user_email=user_email, **kwargs)

    return message_types.VoidMessage()

  @loaner_endpoints.authed_method(
      shelf_message.Shelf,
      shelf_message.ListShelfResponse,
      name='list',
      path='list',
      http_method='POST',
      permission='list_shelves')
  def list_shelves(self, request):
    """List enabled or all shelves based on any shelf attribute."""
    self.check_xsrf_token(self.request_state)
    cursor = None
    if request.page_token:
      cursor = self.get_datastore_cursor(urlsafe_cursor=request.page_token)
    filters = self.to_dict(request, shelf_model.Shelf)

    shelves, next_cursor, additional_results = shelf_model.Shelf.list_shelves(
        next_cursor=cursor, **filters)
    shelf_messages = []
    for shelf in shelves:
      shelf_dict = self.to_dict(shelf, shelf_model.Shelf)
      shelf_messages.append(shelf_message.Shelf(
          enabled=shelf_dict.get('enabled'),
          friendly_name=shelf_dict.get('friendly_name'),
          location=shelf_dict.get('location'),
          latitude=shelf_dict.get('latitude'),
          longitude=shelf_dict.get('longitude'),
          altitude=shelf_dict.get('altitude'),
          capacity=shelf_dict.get('capacity'),
          audit_notification_enabled=shelf_dict.get(
              'audit_notification_enabled'),
          audit_requested=shelf_dict.get('audit_requested'),
          responsible_for_audit=shelf_dict.get('responsible_for_audit'),
          last_audit_time=shelf_dict.get('last_audit_time'),
          last_audit_by=shelf_dict.get('last_audit_by')))
    if next_cursor or additional_results:
      return shelf_message.ListShelfResponse(
          shelves=shelf_messages,
          additional_results=additional_results,
          page_token=next_cursor.urlsafe())
    return shelf_message.ListShelfResponse(shelves=shelf_messages)

  @loaner_endpoints.authed_method(
      shelf_message.ShelfAuditRequest,
      message_types.VoidMessage,
      name='audit',
      path='audit',
      http_method='POST',
      permission='audit_shelf')
  def audit(self, request):
    """Performs an audit on a shelf based on location."""
    self.check_xsrf_token(self.request_state)
    shelf = get_shelf(location=request.location)
    user_email = user.get_user_email()
    devices_on_shelf = []
    devices_retrieved_on_shelf, next_cursor, more = (
        device_model.Device.list_devices(keys_only=True, shelf=shelf.key))
    del next_cursor  # Unused.
    del more  # Unused.
    for device_identifier in request.device_identifiers:
      device = device_model.Device.get(unknown_identifier=device_identifier)
      if not device:
        raise endpoints.NotFoundException(
            _DEVICE_DOES_NOT_EXIST_MSG % device_identifier)
      if device.shelf:
        if device.shelf.get().location is shelf.location:
          devices_on_shelf.append(device.key)
          logging.info('Device %s is already on shelf.', device.serial_number)
          continue
      try:
        device.move_to_shelf(shelf=shelf, user_email=user_email)
        devices_on_shelf.append(device.key)
      except device_model.UnableToMoveToShelfError as err:
        raise endpoints.BadRequestException(str(err))
    for device in devices_retrieved_on_shelf:
      if device not in devices_on_shelf:
        device.get().remove_from_shelf(shelf=shelf, user_email=user_email)
    shelf.audit(user_email=user_email)

    return message_types.VoidMessage()


def get_shelf(location):
  """Gets a shelf using the location.

  Args:
    location: str, the location for a shelf.

  Returns:
    Shelf object.

  Raises:
    endpoints.BadRequestException when a shelf can not be found.
  """
  shelf = shelf_model.Shelf.get(location=location)
  if not shelf:
    raise endpoints.NotFoundException(
        _SHELF_DOES_NOT_EXIST_MSG % location)
  return shelf

