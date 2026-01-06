# from django.contrib import admin
# from .models import TakeoffJob

# @admin.register(TakeoffJob)
# class TakeoffJobAdmin(admin.ModelAdmin):
#     list_display = ['id', 'uploaded_pdf', 'status', 'total_members', 'total_weight_tons', 'uploaded_at']
#     list_filter = ['status', 'uploaded_at']
#     search_fields = ['uploaded_pdf']
#     readonly_fields = ['uploaded_at', 'processing_time', 'total_members', 'total_types', 'total_weight_lbs']
    
#     fieldsets = (
#         ('Upload Information', {
#             'fields': ('uploaded_pdf', 'uploaded_at')
#         }),
#         ('API Configuration', {
#             'fields': ('openai_key', 'gemini_key'),
#             'classes': ('collapse',)
#         }),
#         ('Processing Status', {
#             'fields': ('status', 'processing_time', 'error_message')
#         }),
#         ('Results', {
#             'fields': ('excel_file', 'highlighted_pdf', 'total_members', 'total_types', 'total_weight_lbs')
#         }),
#     )