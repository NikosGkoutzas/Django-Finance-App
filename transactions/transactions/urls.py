from rest_framework_nested import routers
from transactionsApp.views import *
from django.urls import path , include

router = routers.SimpleRouter()
router.register(r'users', CustomUserViewSet)

users_router = routers.NestedSimpleRouter(router, r'users', lookup='user')
users_router.register(r'cards', CardViewSet , basename='user-cards')
users_router.register(r'categories', CategoryViewSet , basename='user-categories')
users_router.register(r'transactions', TransactionViewSet , basename='user-transactions')
users_router.register(r'analytics', AnalyticsViewSet , basename='user-analytics')


urlpatterns = [
                path('', include(router.urls)),
                path('' , include(users_router.urls)),
              ]