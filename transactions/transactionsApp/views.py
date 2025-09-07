from .serializers import *
from .models import *
from rest_framework import viewsets
from rest_framework.views import APIView
from dateutil.relativedelta import relativedelta
from django.utils import timezone



class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer

    





class CardViewSet(viewsets.ModelViewSet):
    serializer_class = CardSerializer

    def get_queryset(self):
        user_id = self.kwargs.get('user_pk')
        return Card.objects.filter(user_id=user_id)

    def perform_create(self , serializer):
        serializer.save(user_id=self.kwargs["user_pk"])


    def list(self , request , *args , **kwargs):
        transaction = Transaction.objects.filter(user_id=self.kwargs['user_pk'] , payment_method='Card' , recurring=True)

        for tr in transaction:
            card = Card.objects.filter(user_id=self.kwargs['user_pk'] , card_number=tr.card_number , 
                                       cvv=tr.cvv , expiration_date=tr.expiration_date).first()

            if(timezone.now().date() == tr.subscription_last_paid_date and tr.subscription_last_paid_date != tr.subscription_end_date):
                delta = relativedelta(days=1)
                if(tr.recurrence_choices == 'Weekly'):
                    delta = relativedelta(weeks=1)
                elif(tr.recurrence_choices == 'Monthly'):
                    delta = relativedelta(months=1)
                elif(tr.recurrence_choices == 'Yearly'):
                    delta = relativedelta(years=1)

                if(tr.type == 'Expense'):
                    if(tr.amount <= card.balance):
                        card.balance -= tr.amount if(card.currency == tr.currency) else Currency_rate.convertion(tr.amount , tr.currency , card.currency)
                        card.save()
                        #tr.message = f'✅ Subsciption transaction for {tr.subscription_last_paid_date} completed successfully.'
                    else:
                        raise serializers.ValidationError(f'❌ Transaction declined: Card balance is too low.')
                
                elif(tr.type == 'Income'):
                    card.balance += tr.amount if(card.currency == tr.currency) else Currency_rate.convertion(tr.amount , tr.currency , card.currency)
                    card.save()
                    #tr.message = f'✅ Subsciption transaction for {tr.subscription_last_paid_date} completed successfully.'

                tr.subscription_last_paid_date += delta
                tr.save()
        return super().list(request , *args , **kwargs)







class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer

    def get_queryset(self):
        user_id = self.kwargs.get('user_pk')
        return Category.objects.filter(user_id=user_id)

    def get_serializer_context(self): # collects user_id from URL (/users/ID/), stores the ID to context['user'] and this info goes to serializer
        context = super().get_serializer_context()
        context['user'] = CustomUser.objects.get(id = self.kwargs['user_pk'])
        return context

    def perform_create(self , serializer):
        serializer.save(user_id = self.kwargs["user_pk"])








class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        user_id = self.kwargs.get('user_pk')
        return Transaction.objects.filter(user_id=user_id)


    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)

        if hasattr(serializer, 'fields'): # check if serializer has fields
            user_pk = self.kwargs.get('user_pk')

            # show the categories of the specific user only
            serializer.fields['category'].queryset = Category.objects.filter(user_id=user_pk)
                
            # show the payment methods of the specific user only
            if(Card.objects.filter(user_id=user_pk)):
                serializer.fields['payment_method'].choices = [('Cash','Cash') , ('Card' , 'Card')]
            else:
                serializer.fields['payment_method'].choices = [('Cash','Cash')]
        
        return serializer
    
    


    def perform_create(self, serializer):
        user = CustomUser.objects.get(pk=self.kwargs.get('user_pk'))
        serializer.save(user=user)




    def list(self , request , *args , **kwargs):
        # If user has a card with balance more than his/her debt, then throw a notification to the user that he/she has a card 
        # with which he/she can pay the debt. The timeframe for the user to pay is (for this example) 5 minutes. If timeframe is passed,
        # then the card that was found which can pay the debt will be deactivated,

        user = CustomUser.objects.get(pk=self.kwargs['user_pk'])
        if(user.debt > 0):
            card = Card.objects.filter(user=user , balance__gte=user.debt).first()
            if(card):
                if(not user.debt_timeframe):
                    user.debt_timeframe = timezone.now() + relativedelta(minutes=5)
                    user.save()

                else:
                    if(timezone.now() < user.debt_timeframe):
                        return Response(f'⚠️ A card was found that can cover your debt. It will be deactivated at {user.debt_timeframe}')
                
                    card.delete()
                    user.debt_timeframe = None
                    user.save()
                    return Response(f'❌ Card \'{str('*')*12}{card.card_number[12:]}\' deactivated. Debt was not settled within the required timeframe.')

        
        return super().list(request , *args , **kwargs)
    



class AnalyticsViewSet(viewsets.ModelViewSet):
    serializer_class = AnalyticsSerializer

    def get_queryset(self , *args , **kwargs):
        user_id = self.kwargs.get('user_pk')
        return Analytics.objects.filter(user_id = user_id)
    
    def get(self , request , pk=None):
        total_card_balance = 0
        for card in Card.objects.filter(user_id=pk):
            total_card_balance += card.balance
        
        data = {
                    'Cash': str(CustomUser.objects.filter(id=pk).first().cash) + str(' ') + str(CustomUser.objects.filter(id=pk).first().currency),
                    #'Total card balance': str(total_card_balance) + str(' ') + str(Card.objects.filter(user_id=pk)).,    se EUR,USD ola mazi se ti? 
                    'Total assets: ': total_card_balance + CustomUser.objects.filter(id=pk).first().cash, # se idio nomisma omws 
                    'Number of categories: ': Category.objects.filter(user_id=pk).count(),
                    'Number of cards: ': Card.objects.filter(user_id=pk).count(),
                    'Number of transactions: ': Transaction.objects.filter(user_id=pk).count(),
                    'Income transactions: ': Transaction.objects.filter(user_id=pk , type='Income').count(),
                    'Expense transactions: ': Transaction.objects.filter(user_id=pk , type='Expense').count()
               }
        
        return Response(data)
    


    def perform_create(self , serializer):
        user_id = CustomUser.objects.filter(id=self.kwargs.get('user_pk'))
        serializer.save(id=user_id)