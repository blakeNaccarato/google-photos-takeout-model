from google_photos_takeout_model.models.bases import ToCamelBaseModel
from google_photos_takeout_model.models.origins import (
    Composition,
    MobileUpload,
    WebUpload,
)


class GooglePhotosCompositionOrigin(ToCamelBaseModel):
    composition: Composition


class GooglePhotosMobileOrigin(ToCamelBaseModel):
    mobile_upload: MobileUpload | ToCamelBaseModel


class GooglePhotosPartnerSharingOrigin(ToCamelBaseModel):
    from_partner_sharing: ToCamelBaseModel


class GooglePhotosSharedAlbumOrigin(ToCamelBaseModel):
    from_shared_album: ToCamelBaseModel


class GooglePhotosWebOrigin(ToCamelBaseModel):
    web_upload: WebUpload
