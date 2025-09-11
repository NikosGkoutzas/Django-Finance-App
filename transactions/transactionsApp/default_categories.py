from .models import Category
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser



#Όταν δημιουργείται ένας νέος χρήστης (created=True), η function create_user_categories καλείται αυτόματα.

@receiver(post_save, sender=CustomUser) 
def create_default_categories(instance , created , **kwargs):
    if(created): # every new user get these default categories
        default_categories = ['Food' , 'Clothing' , 'Transportation' , 'Household bills' , 'Health' , 'Entertainment']
        for category in default_categories:
            Category.objects.get_or_create(title=category , owner=instance)