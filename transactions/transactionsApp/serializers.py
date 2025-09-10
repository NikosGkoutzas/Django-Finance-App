from .models import *
from rest_framework import serializers
from rest_framework.response import Response
from datetime import datetime , date
from django.utils import timezone
from django import forms

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id' , 'username', 'job' , 'cash' , 'debt' , 'currency']

    '''def create(self, data):
        user = CustomUser.objects.create_user(username=data['username'] , password=data['password'] , email=data.get('email'))
        user.is_superuser = True
        user.is_staff = True
        user.save()
        return user'''
    
    def validate(self , data):
        if(data.get('cash') is None):
            data['cash'] = 0.00
        return data


    def to_representation(self , instance):
        rep = super().to_representation(instance)
        if(instance.debt is None):
            CustomUser.objects.filter(debt__isnull=True).update(debt=0.00)
        return rep









class AnalyticsSerializer(serializers.ModelSerializer):
    choose_card = serializers.ChoiceField(choices=[])

    class Meta:
        model = Analytics
        fields = ['all_assets' , 'cash' , 'card' , 'choose_card' , 'income_transactions' , 'expense_transactions' , 'subscriptions' ,
                  'currency' , 'compute_statistics_from' , 'compute_statistics_to']


    def __init__(self , *args , **kwargs):
        user_id = kwargs.pop('user_id', None)
        super().__init__(*args , **kwargs)
        
        if user_id:
            cards = Card.objects.filter(user_id=user_id)
            self.fields['choose_card'].choices = [(f'{card.card_type} - {card.card_number}' , f'{card.card_type} - {card.card_number}') for card in cards]



    def validate(self , data):
        all_assets = data.get('all_assets')
        cash = data.get('cash')
        card = data.get('card')
        subscriptions = data.get('subscriptions')

        if( (all_assets and (cash or card)) or (cash and card) ):
            raise serializers.ValidationError('⚠️ Only one option (All assets, Cash, Card) must be selected.')
        
        if(not all_assets and not cash and not card):
            raise serializers.ValidationError('⚠️ At least one opton (All assets, Cash, Card) must be selected.')
        
        if(not data.get('compute_statistics_from')):
            raise serializers.ValidationError('⚠️ Provide a valid date for the start date.')
        
        if(data.get('compute_statistics_to')):
            if(data.get('compute_statistics_to') < data.get('compute_statistics_from')):
                raise serializers.ValidationError('⚠️ The end date must strictly follow the start date.')
        else:
            raise serializers.ValidationError('⚠️ Provide a valid date for the end date.')
        
        if(cash and subscriptions):
            raise serializers.ValidationError('⚠️ Subscriptions are only available through card payment.')

        return data









class CardSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = Card
        fields = ['id' , 'user' , 'card_type' , 'card_number' , 'cvv' , 'expiration_date' , 'balance' , 'currency']
        read_only_fields = ['card_number' , 'cvv' , 'expiration_date']

    def get_user(self , obj):
        return obj.user.username





class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id' , 'title']


    def validate(self, data):
        user = self.context.get('user')
        if Category.objects.filter(user=user, title__iexact=data.get('title')).exists():
            raise serializers.ValidationError(f"⚠️ This category already exists for this user.")

        return data





class TransactionSerializer(serializers.ModelSerializer):
    card_number = serializers.CharField(required=False)
    cvv = serializers.CharField(required=False)
    expiration_date = serializers.CharField(required=False)
    #category = serializers.SlugRelatedField(slug_field='title' , queryset=Category.objects.all())

    class Meta:
        model = Transaction
        fields = ['id' , 'category' , 'payment_method' , 'card_number' , 'cvv' , 'expiration_date' , 'amount' , 
                  'currency' , 'type' , 'recurring' , 'subscription_start_date' , 'subscription_end_date' , 
                  'recurrence_choices' , 'subscription_next_paid_date', 'message']
        read_only_fields = ['subscription_next_paid_date' , 'message']
    
    def to_representation(self , instance):
        rep = super().to_representation(instance)
        if(instance.payment_method == 'Cash'):
            rep.pop('card_number')
            rep.pop('cvv')
            rep.pop('expiration_date')
            
        if(not instance.recurring):
            rep.pop('subscription_start_date')
            rep.pop('subscription_end_date')
            rep.pop('recurrence_choices')
            rep.pop('recurring')
            rep.pop('subscription_next_paid_date')
        if(not instance.subscription_next_paid_date and instance.subscription_next_paid_date < instance.subscription_start_date):
            rep.pop('subscription_next_paid_date')

        return rep
            



    def validate(self , data):
        payment_method = data.get('payment_method')
        
        # check subscription rules
        if(data.get('recurring')):
            if(data.get('subscription_start_date')):
                if(data.get('subscription_start_date') < timezone.now().date()):
                    raise serializers.ValidationError('⚠️ Provide a valid future date for the subscription start date.')
            else:
                raise serializers.ValidationError('⚠️ Provide a valid date for the subscription start date.')
            
            if(data.get('subscription_end_date')):
                if(data.get('subscription_end_date') <= data.get('subscription_start_date')):
                    raise serializers.ValidationError('⚠️ The subscription end date must strictly follow the subscription start date.')
            else:
                raise serializers.ValidationError('⚠️ Provide a valid date for the subscription end date.')
            

            duration = relativedelta(data.get('subscription_end_date') , data.get('subscription_start_date'))
            if(data.get('recurrence_choices') == 'Weekly'):
                if((data.get('subscription_end_date') - data.get('subscription_start_date')).days % 7 != 0):
                    raise serializers.ValidationError("Subscription duration must be a multiple of whole weeks.")
                
            elif(data.get('recurrence_choices') == 'Monthly'):
                if(duration.days != 0 or duration.years != 0 or duration.months <= 0):
                    raise serializers.ValidationError("Subscription duration must be a multiple of whole months.")
                
            elif(data.get('recurrence_choices') == 'Yearly'):
                if(duration.days != 0 or duration.months != 0 or duration.years <= 0):
                    raise serializers.ValidationError("Subscription duration must be a multiple of whole years.")
                
            
            

        # card usage
        if(payment_method == 'Card'):
            card_number = data.get('card_number')
            cvv = data.get('cvv')
            expir_date = data.get('expiration_date')

            # check card_number
            if(not card_number or len(card_number) != 16):
                raise serializers.ValidationError('⚠️ Card must contain 16 digits!')
            
            if(not card_number or not card_number.isdigit()):
                raise serializers.ValidationError('⚠️ Card must contains only digits.')

            # check cvv
            if(not cvv or len(cvv) != 3):
                raise serializers.ValidationError('⚠️ CVV must contain 3 digits!')
            
            if(not cvv or not cvv.isdigit()):
                raise serializers.ValidationError('⚠️ CVV must contains only digits.')
            
            # check expiration_date
            if(not expir_date or not (len(expir_date) == 5 and expir_date[:2].isdigit() and expir_date[2] == '/' and expir_date[3:].isdigit())):
                raise serializers.ValidationError('⚠️ Expiration date is wrong')
            if(int(expir_date[0]) == 0):
                if not (int(expir_date[1]) >= 1 and int(expir_date[1]) <= 9):
                    raise serializers.ValidationError('⚠️ Expiration date is wrong')
                if(int(expir_date[1]) < date.today().month and int(expir_date[3:]) == int(str(date.today().year)[2:])):
                    raise serializers.ValidationError('❌ Card expired!')
            if(expir_date[0] != 0):
                if not (int(expir_date[:2]) >= 1 and int(expir_date[:2]) <= 12):
                    raise serializers.ValidationError('⚠️ Expiration date is wrong')
                if(int(expir_date[:2]) < date.today().month and int(expir_date[3:]) == int(str(date.today().year)[2:])):
                    raise serializers.ValidationError('❌ Card expired!')
            if(int(expir_date[3:]) < int(str(date.today().year)[2:])):
                raise serializers.ValidationError('❌ Card expired!')
            if(int(expir_date[3:]) == int(str(date.today().year)[2:]) and int(expir_date[:2]) < date.today().month ):
                raise serializers.ValidationError('❌ Card expired!')
            
        return data







    def create(self , validated_data):
        payment_method = validated_data.get('payment_method')
        type = validated_data.get('type')
        amount = validated_data.get('amount')
        currency = validated_data.get('currency')
        user = validated_data.get('user')
        recurring = validated_data.get('recurring')
        subscription_start_date = validated_data.get('subscription_start_date')
        subscription_end_date = validated_data.get('subscription_end_date')
        category = validated_data.get('category')

        # card usage
        if(payment_method == 'Card'):
            recurrence_choices = validated_data.get('recurrence_choices')

            card = Card.objects.filter(user=user , card_number=validated_data.get('card_number') , 
                                    cvv=validated_data.get('cvv') , 
                                    expiration_date=validated_data.get('expiration_date')).first()
            
            # card not found
            if(not card):
                raise serializers.ValidationError(f"Card '{str('*')*12}{str(validated_data.get('card_number'))[12:]}' not found")  
            
            # check credit card limit
            if(card.card_type == 'Credit Card'):
                if(type == 'Expense'):
                    if(amount > CREDIT_LIMIT):
                        raise serializers.ValidationError(f"❌ Transaction declined. Credit limit of {CREDIT_LIMIT} {card.currency} exceeded.")

            if(type == 'Income'):
                if(not recurring):
                    card.balance += amount if(card.currency == currency) else Currency_rate.convertion(amount , currency , card.currency)
                    card.save()
                    transaction = super().create(validated_data)
                    transaction.message = '✅ Transaction completed successfully.'
                    transaction.save()
                    return transaction
                
                else:
                    choice = 'day'
                    if(recurrence_choices == 'Weekly'):
                        choice = 'week'
                    elif(recurrence_choices == 'Monthly'):
                        choice = 'month'
                    elif(recurrence_choices == 'Yearly'):
                        choice = 'year'
                    
                    transaction = super().create(validated_data)
                    transaction.subscription_next_paid_date = subscription_start_date
                    transaction.message = f'✅ Subscription period: {subscription_start_date} / {subscription_end_date}. Every {choice} {amount} {card.currency} will be credited to the user\'s card.'
                    transaction.save()
                    return transaction

            elif(type == 'Expense'):
                debt_category = Category.objects.filter(user=user , title__iexact='debt').first()
                if(debt_category and category == debt_category):
                    
                    if(card.balance < amount):
                        raise serializers.ValidationError(f'❌ Transaction declined: Card balance is too low.')

                    debt = user.debt
                    user.debt -= amount if(card.currency == currency) else Currency_rate.convertion(amount , currency , card.currency)
                    if(user.debt < 0):
                        raise serializers.ValidationError(f'⚠️ Attention! Your amount exceeds the debt you must pay. Debt is {debt} {user.currency}')
                    user.save()
                    transaction = super().create(validated_data)
                    transaction.message = f'✅ Transaction completed successfully. Debt is {user.debt} {card.currency}.'
                    transaction.save()
                    return transaction
                
                else:
                    if(user.debt > 0):
                        # if a card of the user has balance lower than his/her debt, then just abort all his/her expense transactions
                        if(Card.objects.filter(user=user , balance__gte=user.debt).exists()):
                            raise serializers.ValidationError('❌ New transactions cannot be processed until debt is cleared.')

                if(not recurring):
                    if(card.balance < amount):
                        user.debt += amount if(card.currency == currency) else Currency_rate.convertion(amount , currency , card.currency)
                        user.save()
                        raise serializers.ValidationError(f'❌ Transaction declined: Card balance is too low. A debt of {amount} {card.currency} has been imposed.')
                    
                    card.balance -= amount if(card.currency == currency) else Currency_rate.convertion(amount , currency , card.currency)
                    card.save()
                    transaction = super().create(validated_data)
                    transaction.message = '✅ Transaction completed successfully.'
                    transaction.save()
                    return transaction
                
                elif(recurring):
                    choice = 'day'
                    if(recurrence_choices == 'Weekly'):
                        choice = 'week'
                    elif(recurrence_choices == 'Monthly'):
                        choice = 'month'
                    elif(recurrence_choices == 'Yearly'):
                        choice = 'year'

                    transaction = super().create(validated_data)
                    transaction.subscription_next_paid_date = subscription_start_date
                    transaction.message = f'✅ Subscription period: {subscription_start_date} / {subscription_end_date}. Every {choice} {amount} {card.currency} will be credited from the user\'s card.'
                    transaction.save()
                    return transaction
                    

        # cash usage
        else:
            if(recurring):
                raise serializers.ValidationError('⚠️ Recurring payments are only permitted via card.')
            
            # do not inlcude card details
            validated_data['card_number'] = None
            validated_data['cvv'] = None
            validated_data['expiration_date'] = None
            
            if(type == 'Income'):
                if(not recurring):
                    user.cash += amount if(user.currency == currency) else Currency_rate.convertion(amount , currency , user.currency)
                    user.save()
                    transaction = super().create(validated_data)
                    transaction.message = '✅ Transaction completed successfully.'   
                    transaction.save()
                    return transaction
                
            elif(type == 'Expense'):
                debt_category = Category.objects.filter(user=user , title__iexact='debt').first()
                if(str(category) == str(debt_category.title)):
                    if(user.cash < amount):
                        raise serializers.ValidationError(f'❌ Transaction declined: Cash are too low.')

                    debt = user.debt
                    user.debt -= amount if(user.currency == currency) else Currency_rate.convertion(amount , currency , user.currency)

                    if(user.debt < 0):
                        raise serializers.ValidationError(f'⚠️ Attention! Your amount exceeds the debt you must pay. Debt is {debt} {user.currency}')
                    user.save()
                    transaction = super().create(validated_data)
                    transaction.message = f'✅ Transaction completed successfully. Debt is {user.debt} {user.currency}.'
                    transaction.save()
                    return transaction
                
                else:
                    if(user.debt > 0):
                        # if a card of the user has balance lower than his/her debt, then just abort all his/her expense transactions
                        if(Card.objects.filter(user=user , balance__gte=user.debt).exists()):
                            raise serializers.ValidationError('❌ New transactions cannot be processed until debt is cleared.')
                        
                if(not recurring):
                    if(user.cash < amount):
                        user.debt += amount if(user.currency == currency) else Currency_rate.convertion(amount , currency , user.currency)
                        user.save()
                        raise serializers.ValidationError(f'❌ Transaction declined. Cash are too low. A debt of {amount} {user.currency} has been imposed.')

                    user.cash -= amount if(user.currency == currency) else Currency_rate.convertion(amount , currency , user.currency)
                    user.save()
                    transaction = super().create(validated_data)
                    transaction.message = '✅ Transaction completed successfully.'
                    transaction.save()
                    return transaction
