# apps/cuentas/pagination.py
from rest_framework.pagination import CursorPagination

class BitacoraCursorPagination(CursorPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
    ordering = "-timestamp"  # cursor ordena según este campo
    cursor_query_param = "cursor"