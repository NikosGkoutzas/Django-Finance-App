from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from decimal import Decimal
import random
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.core.validators import MinValueValidator , MaxValueValidator


CREDIT_LIMIT = 1000 # credit cards have limits for every currency


class Currency_rate:
    # rates in relation to EUR.
    currency_rates = {
        'EUR':1.00,
        'USD':1.16,
        'GBP':0.85,
        'JPY':171.00,
        'SEK':11.56,
        'CHF':1.09
    }

    @staticmethod
    def convertion(amount , initial_currency , goal_currency):
        euro_amount = amount / Decimal(Currency_rate.currency_rates[initial_currency])
        goal_cur_amount = euro_amount * Decimal(Currency_rate.currency_rates[goal_currency])
        return goal_cur_amount






class Currency:
    currency = [('EUR' , 'EUR (€)'),
                ('USD' , 'USD ($)'),
                ('GBP' , 'GBP (£)'),
                ('JPY' , 'JPY (¥)'),
                ('SEK' , 'SEK (Kr)'),
                ('CHF' , 'CHF (₣)')
            ]
    





class Transaction_methods:
    methods = [('Credit Card' , 'Credit Card'),
               ('Debit Card' , 'Debit Card'),
               ('Prepaid Card' , 'Prepaid Card'),
               ('Virtual Card' , 'Virtual Card')
              ]






class CustomUser(AbstractUser):
    username = models.CharField(max_length=150 , unique=True , verbose_name='Username*')
    job = models.CharField(max_length=100 , blank=True , null=True)
    cash = models.DecimalField(max_digits=12 , decimal_places=2 , blank=False , null=False , default=0 , 
                               validators=[MinValueValidator(0) , MaxValueValidator(10000)] , verbose_name='Cash*')
    debt = models.DecimalField(max_digits=12 , decimal_places=2 , blank=True , null=True , default=0)
    debt_timeframe = models.DateTimeField(blank=True , null=True)
    currency = models.CharField(max_length=10 , blank=False , null=False , choices=Currency.currency , verbose_name='Currency*')

    def __str__(self):
        return self.username






# create multiple cards for users
class Card(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL , on_delete=models.CASCADE) # if user is deleted, card must be deleted
    card_type = models.CharField(max_length=20 , default='Prepaid Card' , choices=Transaction_methods.methods , verbose_name='Card type*')
    card_number = models.CharField(max_length=16 , unique=True)
    cvv = models.CharField(max_length=3)
    expiration_date = models.CharField(max_length=10)
    balance = models.DecimalField(max_digits=12 , decimal_places=2 , blank=False , null=False ,
                                  validators=[MinValueValidator(0) , MaxValueValidator(100000)] , verbose_name='Balance*')
    currency = models.CharField(max_length=10 , choices=Currency.currency , default=('EUR' , 'EUR (€)') , verbose_name='Currency*')


    def save(self , *args , **kwargs):
        if(not self.pk):
            cvv = ''.join([str(random.randint(0,9)) for _ in range(3)])
            year = str((timezone.now().today() + relativedelta(years=random.randint(1,7))).year)[2:]
            month = str(random.randint(1,12))
            month = '0' + month if int(month) < 10 else month            
            expiration_date = f'{month}' + '/' + f'{year}'
            self.cvv = cvv
            self.expiration_date = expiration_date

            while(1):
                number = ''.join([str(random.randint(0,9)) for _ in range(16)])
                if(not Card.objects.filter(card_number=number).exists()):
                    self.card_number = number
                    break
        super().save(*args , **kwargs)


    #def __str__(self):
    #    return self.user.username







class Category(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL , on_delete=models.CASCADE)
    title = models.CharField(max_length=50 , verbose_name='Title*')

    def __str__(self):
        return self.title
    





class Transaction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL , on_delete=models.CASCADE)
    payment_method = models.CharField(max_length=10 , choices=[('Cash' , 'Cash'),
                                                               ('Card' , 'Card')
                                                              ] , 
                                      default='Cash' , verbose_name='Payment method*'
                                     )
    card_number = models.CharField(max_length=16 , blank=True , null=True , help_text='Insert your 16-digit number card.')
    cvv = models.CharField(max_length=3 , blank=True , null=True , help_text='Insert your CVV number.')
    expiration_date = models.CharField(max_length=10 , blank=True , null=True , help_text='Example: 04/26')
    amount = models.DecimalField(max_digits=12 , decimal_places=2 , blank=False , null=False , 
                                 validators=[MinValueValidator(0.01) , MaxValueValidator(10000)] , verbose_name='Amount*')
    currency = models.CharField(max_length=10 , blank=False , null=False , choices=Currency.currency , verbose_name='Currency*')
    type = models.CharField(max_length=10 , choices=[('Income' , 'Income'),
                                                     ('Expense' , 'Expense')
                                                    ] , 
                            default='Expense' , verbose_name='Type*'
                           )
    transaction_date = models.DateField(auto_now=True)
    category = models.ForeignKey(Category , blank=False , null=False , on_delete=models.CASCADE , verbose_name='Category*')
    recurring = models.BooleanField(help_text='Subscription payments are only permitted via card.')
    subscription_start_date = models.DateField(blank=True , null=True)
    subscription_end_date = models.DateField(blank=True , null=True)
    recurrence_choices = models.CharField(max_length=10 , choices=[('Daily' , 'Daily'),
                                                                   ('Weekly' , 'Weekly'),
                                                                   ('Monthly' , 'Monthly'),
                                                                   ('Yearly' , 'Yearly')
                                                                  ]
                                         )
    subscription_next_paid_date = models.DateField(blank=True , null=True , default=timezone.now().date())
    message = models.CharField(max_length=200 , blank=True , null=True)







class Analytics(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL , on_delete=models.CASCADE)
    all_assets = models.BooleanField(default=False)
    cash = models.BooleanField(default=False)
    card = models.BooleanField(default=False)
    choose_card = models.CharField(max_length=40)
    income_transactions = models.BooleanField(default=False)
    expense_transactions = models.BooleanField(default=False)
    subscriptions = models.BooleanField(default=False)
    compute_statistics_from = models.DateField(blank=True , null=True , verbose_name='From')
    compute_statistics_to = models.DateField(blank=True , null=True , verbose_name='Until')
    currency = models.CharField(max_length=10 , choices=Currency.currency , default=('EUR' , 'EUR (€)'))