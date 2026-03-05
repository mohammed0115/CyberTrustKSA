"""AI Engine URLs - Chatbot API routing."""
from django.urls import path

from . import views

app_name = "ai_engine"

urlpatterns = [
    # Chatbot API
    path("api/chatbot/message/", views.chatbot_message, name="chatbot_message"),
    path("api/chatbot/message/<slug:slug>/", views.chatbot_message, name="chatbot_message_org"),
    path("api/chatbot/history/", views.chatbot_history, name="chatbot_history"),
    path("api/chatbot/history/<slug:slug>/", views.chatbot_history, name="chatbot_history_org"),
    path("api/chatbot/clear/", views.chatbot_clear, name="chatbot_clear"),
    path("api/chatbot/clear/<slug:slug>/", views.chatbot_clear, name="chatbot_clear_org"),
    
    # Remediation API
    path("api/remediation/<int:control_id>/template/", views.get_remediation_template, name="remediation_template"),
    path("api/remediation/<int:control_id>/template/<slug:slug>/", views.get_remediation_template, name="remediation_template_org"),
    path("api/remediation/<int:control_id>/templates/", views.list_remediation_templates, name="remediation_templates"),
    path("api/remediation/<int:control_id>/track/", views.track_remediation, name="track_remediation"),
    path("api/remediation/<int:control_id>/track/<slug:slug>/", views.track_remediation, name="track_remediation_org"),
]
