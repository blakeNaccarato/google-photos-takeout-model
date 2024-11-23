from google_photos_takeout_model.models.bases import (
    ToCamelBaseModel,
)


class Composition(ToCamelBaseModel):
    type: str


class WebUpload(ToCamelBaseModel):
    computer_upload: ToCamelBaseModel


class DeviceFolder(ToCamelBaseModel):
    local_folder_name: str


class MobileUpload(ToCamelBaseModel):
    device_folder: DeviceFolder
    device_type: str
