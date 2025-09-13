from .serializers import *
from .models import *
from rest_framework import viewsets
from rest_framework.response import Response
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

            if(timezone.now().date() == tr.subscription_next_paid_date and tr.subscription_next_paid_date != tr.subscription_end_date):
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
                        #tr.message = f'✅ Subsciption transaction for {tr.subscription_next_paid_date} completed successfully.'
                    else:
                        raise serializers.ValidationError(f'❌ Transaction declined: Card balance is too low.')
                
                elif(tr.type == 'Income'):
                    card.balance += tr.amount if(card.currency == tr.currency) else Currency_rate.convertion(tr.amount , tr.currency , card.currency)
                    card.save()
                    #tr.message = f'✅ Subsciption transaction for {tr.subscription_next_paid_date} completed successfully.'

                tr.subscription_next_paid_date += delta
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
                        return Response(f'⚠️ A card was found that can cover your debt. It will be deactivated at {user.debt_timeframe.strftime("%d-%m-%Y, %H:%M:%S")}')
                
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
    
    
    def get_serializer(self , *args , **kwargs):
        kwargs['user_id'] = self.kwargs.get('user_pk')
        return super().get_serializer(*args, **kwargs)
    
    

    def create(self , request , *args , **kwargs):
        user_id = self.kwargs.get('user_pk')
        serializer = AnalyticsSerializer(data = request.data , user_id = user_id)
        serializer.is_valid(raise_exception = True)
        data = serializer.validated_data

        user = CustomUser.objects.filter(id=user_id).first()
        all_assets = data.get('all_assets')
        cash = data.get('cash')
        card = data.get('card')
        income_transactions = data.get('income_transactions')
        expense_transactions = data.get('expense_transactions')
        subscriptions = data.get('subscriptions')
        currency = data.get('currency')
        compute_statistics_from = data.get('compute_statistics_from')
        compute_statistics_to = data.get('compute_statistics_to')
        choose_card = str(data.get('choose_card')).strip('-').split()[3]
        selected_card = data.get('choose_card')
        message = []
        cards_balances = []
        transactions = Transaction.objects.filter(user=user ,
                                                  transaction_date__gte = compute_statistics_from ,
                                                  transaction_date__lte = compute_statistics_to
                                                  )
        
        

        if(all_assets):
            total_cash = user.cash if(user.currency == currency) else Currency_rate.convertion(user.cash , user.currency , currency)
            total_card_balance = 0
            for card in Card.objects.filter(user_id=user_id):
                total_card_balance += (card.balance if(card.currency == currency) else Currency_rate.convertion(card.balance , card.currency , currency))
                card_balance = (card.balance if(card.currency == currency) else Currency_rate.convertion(card.balance , card.currency , currency))
                cards_balances.append(f'{card.card_type} - {card.card_number}  ->  {card_balance:.2f} {currency}')
            message.append( f'Total assets: {total_cash + total_card_balance:.2f} {currency}' )
            message.append('Total cash: ' f'{total_cash:.2f} {currency}')
            message.append('Total card balance: ' f'{total_card_balance:.2f} {currency}')
            message.append(cards_balances)

            total_income_cash = 0
            total_income_card = 0
            total_expenses_cash = 0
            total_expenses_card = 0
            total_incomes_subscriptions = 0
            total_expenses_subscriptions = 0

            for tr in transactions:
                this_card = Card.objects.filter(user=user , card_number=tr.card_number).first()
                if(tr.type == 'Income'):
                    if(tr.payment_method == 'Cash'):
                        total_income_cash += (tr.amount if(tr.currency == currency) else Currency_rate.convertion(tr.amount , tr.currency , currency))
                    if(tr.payment_method == 'Card' and this_card):
                        total_income_card += (tr.amount if(tr.currency == currency) else Currency_rate.convertion(tr.amount , tr.currency , currency))
                    if(tr.recurring):
                        total_incomes_subscriptions += (tr.amount if(tr.currency == currency) else Currency_rate.convertion(tr.amount , tr.currency , currency))

                if(tr.type == 'Expense'):
                    if(tr.payment_method == 'Cash'):
                        total_expenses_cash += (tr.amount if(tr.currency == currency) else Currency_rate.convertion(tr.amount , tr.currency , currency))
                    if(tr.payment_method == 'Card' and this_card):
                        total_expenses_card += (tr.amount if(tr.currency == currency) else Currency_rate.convertion(tr.amount , tr.currency , currency))
                    if(tr.recurring):
                        total_expenses_subscriptions += (tr.amount if(tr.currency == currency) else Currency_rate.convertion(tr.amount , tr.currency , currency))

            message.append(f'Total incomes in cash: {total_income_cash:.2f} {currency}')
            message.append(f'Total incomes in card: {total_income_card:.2f} {currency}')
            message.append(f'Total expenses in cash: {total_expenses_cash:.2f} {currency}')
            message.append(f'Total expenses in card: {total_expenses_card:.2f} {currency}')
            message.append(f'Total incomes subscriptions: {total_incomes_subscriptions:.2f} {currency}')
            message.append(f'Total expenses subscriptions: {total_expenses_subscriptions:.2f} {currency}')



        elif(cash):
            total_cash = user.cash if(user.currency == currency) else Currency_rate.convertion(user.cash , user.currency , currency)
            message.append('Total cash: ' f'{total_cash:.2f} {currency}')

            total_income_cash = 0
            total_expense_cash = 0
            for tr in transactions:
                if(tr.type == 'Income' and tr.payment_method == 'Cash'):
                    total_income_cash += (tr.amount if(tr.currency == currency) else Currency_rate.convertion(tr.amount , tr.currency , currency))

                elif(tr.type == 'Expense' and tr.payment_method == 'Cash' and expense_transactions):
                    total_expense_cash += (tr.amount if(tr.currency == currency) else Currency_rate.convertion(tr.amount , tr.currency , currency))

            if(income_transactions):
                message.append(f'Total incomes in cash: {total_income_cash:.2f} {currency}')

            if(expense_transactions):
                message.append(f'Total expenses in cash: {total_expense_cash:.2f} {currency}')
            
            elif(not income_transactions and not expense_transactions):
                message.append(f'Total incomes in cash: {total_income_cash:.2f} {currency}')
                message.append(f'Total expenses in cash: {total_expense_cash:.2f} {currency}')
        

        elif(card):
            total_card_balance = 0
            for card in Card.objects.filter(user_id=user_id):
                total_card_balance += (card.balance if(card.currency == currency) else Currency_rate.convertion(card.balance , card.currency , currency))
                card_balance = (card.balance if(card.currency == currency) else Currency_rate.convertion(card.balance , card.currency , currency))
                cards_balances.append(f'{card.card_type} - {card.card_number}  ->  {card_balance:.2f} {currency}')
            message.append('Total card balance: ' f'{total_card_balance:.2f} {currency}')
            message.append(cards_balances)

            total_income_card = 0
            total_expenses_card = 0
            total_incomes_subscriptions = 0
            total_expenses_subscriptions = 0

            for tr in transactions:
                chosen_card = Card.objects.filter(user=user , card_number=tr.card_number).first()
                if(chosen_card and tr.card_number == choose_card):
                    if(tr.type == 'Income'):
                        if(tr.payment_method == 'Card'):
                            total_income_card += (tr.amount if(tr.currency == currency) else Currency_rate.convertion(tr.amount , tr.currency , currency))
                        if(tr.recurring):
                            total_incomes_subscriptions += (tr.amount if(tr.currency == currency) else Currency_rate.convertion(tr.amount , tr.currency , currency))

                    if(tr.type == 'Expense'):
                        if(tr.payment_method == 'Card'):
                            total_expenses_card += (tr.amount if(tr.currency == currency) else Currency_rate.convertion(tr.amount , tr.currency , currency))
                        if(tr.recurring):
                            total_expenses_subscriptions += (tr.amount if(tr.currency == currency) else Currency_rate.convertion(tr.amount , tr.currency , currency))
                    
                    if(subscriptions):
                        if(tr.recurring):
                            if(tr.type == 'Income'):
                                total_incomes_subscriptions += (tr.amount if(tr.currency == currency) else Currency_rate.convertion(tr.amount , tr.currency , currency))
                            if(tr.type == 'Expense'):
                                total_expenses_subscriptions += (tr.amount if(tr.currency == currency) else Currency_rate.convertion(tr.amount , tr.currency , currency))

            if(income_transactions):
                message.append(f'Total incomes with \'{selected_card}\': {total_income_card:.2f} {currency}')
                if(subscriptions):
                    message.append(f'Total incomes subscriptions with \'{selected_card}\': {total_incomes_subscriptions:.2f} {currency}')
            if(expense_transactions):
                message.append(f'Total expenses with \'{selected_card}\': {total_expenses_card:.2f} {currency}')
                if(subscriptions):
                    message.append(f'Total expenses subscriptions with \'{selected_card}\': {total_expenses_subscriptions:.2f} {currency}')
            elif(subscriptions and not income_transactions and not expense_transactions):
                message.append(f'Total incomes subscriptions with \'{selected_card}\': {total_incomes_subscriptions:.2f} {currency}')
                message.append(f'Total expenses subscriptions with \'{selected_card}\': {total_expenses_subscriptions:.2f} {currency}')
            elif(not income_transactions and not expense_transactions and not subscriptions):
                message.append(f'Total incomes with \'{selected_card}\': {total_income_card:.2f} {currency}')
                message.append(f'Total expenses with \'{selected_card}\': {total_expenses_card:.2f} {currency}')
                message.append(f'Total incomes subscriptions with \'{selected_card}\': {total_incomes_subscriptions:.2f} {currency}')
                message.append(f'Total expenses subscriptions with \'{selected_card}\': {total_expenses_subscriptions:.2f} {currency}')

        return Response(message)