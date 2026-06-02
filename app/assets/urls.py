from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/',                    views.dashboard,              name='dashboard'),
    path('assets/',                       views.asset_list,             name='asset_list'),
    path('assets/create/',                views.asset_create,           name='asset_create'),
    path('assets/bulk-update/',           views.asset_bulk_update,      name='asset_bulk_update'),
    path('assets/<int:pk>/',              views.asset_detail,           name='asset_detail'),
    path('assets/<int:pk>/edit/',         views.asset_edit,             name='asset_edit'),
    path('assets/<int:pk>/delete/',       views.asset_delete,           name='asset_delete'),
    path('maintenance/',                  views.maintenance_list,       name='maintenance_list'),
    path('maintenance/create/',           views.maintenance_create,     name='maintenance_create'),
    path('maintenance/<int:pk>/edit/',    views.maintenance_edit,       name='maintenance_edit'),
    path('maintenance/<int:pk>/delete/',  views.maintenance_delete,     name='maintenance_delete'),
    path('maintenance/<int:pk>/',         views.maintenance_detail,     name='maintenance_detail'),
    path('maintenance/<int:pk>/approve/', views.maintenance_approve,    name='maintenance_approve'),
    path('mileage/',                      views.mileage_log,            name='mileage_log'),
    # Asset Requests
    path('asset-requests/',               views.asset_request_list,     name='asset_request_list'),
    path('asset-requests/new/',           views.asset_request_create,   name='asset_request_create'),
    path('asset-requests/<int:pk>/review/', views.asset_request_review, name='asset_request_review'),
    path('asset-requests/<int:pk>/delete/', views.asset_request_delete, name='asset_request_delete'),
    # Maintenance Technician Portal
    path('maintenance-portal/',           views.maintenance_portal,     name='maintenance_portal'),
    path('maintenance-portal/notifications/', views.maintenance_notifications, name='maintenance_notifications'),
    path('maintenance-portal/notifications/<int:pk>/read/', views.maintenance_notification_mark_read, name='notification_mark_read'),
]