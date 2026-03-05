
from importlib import import_module

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlconf_module = "webui.urls"
try:
    import_module(urlconf_module)
except ModuleNotFoundError as exc:
    if exc.name != "webui":
        raise
    urlconf_module = "cybertrust.webui.urls"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include((urlconf_module, "webui"), namespace="webui")),
    path("api/", include("cybertrust.apps.accounts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
