# Copyright (C) 2026 Redcar & Cleveland Borough Council
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from django.urls import path

from . import views
from .class_views import EnquiryListView, EnquiryDetailView, EnquiryCloseView
from .datatables_views import enquiry_list_datatables
from .export_views import export_enquiries_csv, export_enquiries_excel, get_export_info
from .file_management_views import (
    file_management_dashboard, run_storage_analysis, cleanup_orphaned_files,
    optimize_summernote_images, optimize_summernote_images_stream, file_browser, file_browser_data, storage_analytics_api,
    check_missing_images, update_attachment_sizes
)

app_name = 'application'

urlpatterns = [
    # Authentication and main pages
    path('', views.welcome, name='welcome'),
    path('home/', views.index, name='index'),
    path('logout/', views.logout_view, name='logout'),

    # Enquiry URLs - Mix of class-based and function-based views
    path('enquiries/', EnquiryListView.as_view(), name='enquiry_list'),
    path('enquiries/<int:pk>/', EnquiryDetailView.as_view(), name='enquiry_detail'),
    path('enquiries/create/', views.enquiry_create, name='enquiry_create'),
    path('enquiries/<int:pk>/edit/', views.enquiry_edit, name='enquiry_edit'),
    path('enquiries/<int:pk>/close/', EnquiryCloseView.as_view(), name='enquiry_close'),
    path('enquiries/<int:pk>/reopen/', views.enquiry_reopen, name='enquiry_reopen'),
    path('enquiries/<int:pk>/add-email-note/', views.api_add_email_note, name='api_add_email_note'),
    # Email functionality integrated into Create Enquiry form

    # Reports
    path('reports/average-response-time/', views.average_response_time_report, name='average_response_time_report'),
    path('reports/overdue-enquiries/', views.overdue_enquiries_report, name='overdue_enquiries_report'),
    path('reports/enquiries-per-member/', views.enquiries_per_member_report, name='enquiries_per_member_report'),
    path('reports/enquiries-per-member-monthly/', views.enquiries_per_member_monthly_report, name='enquiries_per_member_monthly_report'),
    path('reports/enquiries-per-section/', views.enquiries_per_section_report, name='enquiries_per_section_report'),
    path('reports/enquiries-per-section-monthly/', views.enquiries_per_section_monthly_report, name='enquiries_per_section_monthly_report'),
    path('reports/enquiries-per-job/', views.enquiries_per_job_report, name='enquiries_per_job_report'),
    path('reports/enquiries-per-job-monthly/', views.enquiries_per_job_monthly_report, name='enquiries_per_job_monthly_report'),
    path('reports/enquiries-per-ward/', views.enquiries_per_ward_report, name='enquiries_per_ward_report'),
    path('reports/enquiries-per-ward-monthly/', views.enquiries_per_ward_monthly_report, name='enquiries_per_ward_monthly_report'),
    path('reports/monthly-enquiries/', views.monthly_enquiries_report, name='monthly_enquiries_report'),
    path('reports/enquiries-by-section/<int:section_id>/', views.enquiries_by_section, name='enquiries_by_section'),
    path('reports/enquiries-by-contact/<int:contact_id>/', views.enquiries_by_contact, name='enquiries_by_contact'),
    path('reports/enquiries-by-jobtype/<int:jobtype_id>/', views.enquiries_by_jobtype, name='enquiries_by_jobtype'),

    # Chart Reports
    path('reports/performance-dashboard/', views.performance_dashboard_report, name='performance_dashboard_report'),
    path('reports/section-workload-chart/', views.section_workload_chart_report, name='section_workload_chart_report'),
    path('reports/job-workload-chart/', views.job_workload_chart_report, name='job_workload_chart_report'),

    # DataTables server-side processing
    path('api/enquiries-datatables/', enquiry_list_datatables, name='enquiry_list_datatables'),
    
    # Server-side exports
    path('api/export/csv/', export_enquiries_csv, name='export_enquiries_csv'),
    path('api/export/excel/', export_enquiries_excel, name='export_enquiries_excel'),
    path('api/export/info/', get_export_info, name='get_export_info'),
    
    # API endpoints for AJAX lookups - Simplified
    path('api/search-job-types/', views.api_search_job_types, name='api_search_job_types'),
    path('api/get-all-job-types/', views.api_get_all_job_types, name='api_get_all_job_types'),
    path('api/get-all-contacts/', views.api_get_all_contacts, name='api_get_all_contacts'),
    path('api/get-contacts-by-job-type/', views.api_get_contacts_by_job_type, name='api_get_contacts_by_job_type'),
    path('api/get-job-types-by-contact/', views.api_get_job_types_by_contact, name='api_get_job_types_by_contact'),
    path('api/update-closed-enquiry-job-type/', views.api_update_closed_enquiry_job_type, name='api_update_closed_enquiry_job_type'),
    path('api/get-contact-section/', views.api_get_contact_section, name='api_get_contact_section'),
    path('api/parse-email/', views.api_parse_email, name='api_parse_email'),
    path('api/parse-email-update/', views.api_parse_email_update, name='api_parse_email_update'),
    path('api/find-member-by-email/', views.api_find_member_by_email, name='api_find_member_by_email'),
    path('api/upload-photos/', views.api_upload_photos, name='api_upload_photos'),
    path('api/delete-attachment/<int:attachment_id>/', views.api_delete_attachment, name='api_delete_attachment'),

    # Image upload for Summernote - OPTIONAL (base64 embedding is default)
    # Uncomment if you want file-based image storage instead of base64
    # path('upload-image/', views.upload_image, name='upload_image'),

    # File Management URLs
    path('file-management/', file_management_dashboard, name='file_management_dashboard'),
    path('file-management/analysis/', run_storage_analysis, name='run_storage_analysis'),
    path('file-management/cleanup/', cleanup_orphaned_files, name='cleanup_orphaned_files'),
    path('file-management/check-missing/', check_missing_images, name='check_missing_images'),
    path('file-management/update-sizes/', update_attachment_sizes, name='update_attachment_sizes'),
    path('file-management/optimize/', optimize_summernote_images, name='optimize_summernote_images'),
    path('file-management/optimize/stream/', optimize_summernote_images_stream, name='optimize_summernote_images_stream'),
    path('file-browser/', file_browser, name='file_browser'),
    path('file-browser/data/', file_browser_data, name='file_browser_data'),
    path('api/storage-analytics/', storage_analytics_api, name='storage_analytics_api'),

]