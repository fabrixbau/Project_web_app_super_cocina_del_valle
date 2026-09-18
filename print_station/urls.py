from django.urls import path

from . import views

app_name = "print_station"
urlpatterns = [
    path("solicitar/", views.request_print, name="request"),
    path("estado/<int:job_id>/", views.job_status, name="status"),
    path("agente/tomar/", views.claim_job, name="claim"),
    path("agente/<int:job_id>/finalizar/", views.finish_job, name="finish"),
    path("agente/latido/", views.agent_heartbeat, name="heartbeat"),
]
