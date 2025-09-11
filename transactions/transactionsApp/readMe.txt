USER
username
password
email (unique)
birth_date (today-birth_date >= 18)
job (null=True)




CATEGORY
title




TRANSACTION
amount
currency (EUR , USD , GBP , YEN , SEK , CHF)
type (income , expense)
Date (date of transaction)
category (in which category this transaction belongs to)
recurring (True , False)
start_recurring_date (null=True)
recurrence_choices (daily , weekly , monthly , yearly)
owner
start_recurring_date: must not be null if recurring is True
recurrence_choices: must not be null if recurring is True




And finally compute statistics and
Get alerts if expense > income of month
convert in other currency