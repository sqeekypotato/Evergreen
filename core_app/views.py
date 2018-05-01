from __future__ import unicode_literals

from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.core.mail import EmailMessage
from django.views.generic import View
from django_pandas.io import read_frame

import pandas as pd
import threading

from core_app.forms import ContactForm, UploadToExistingAccount, UploadFileForm, AccountSelectForm, YearForm, MonthForm,\
    CategorySelection, IncomeCategorySelection
from core_app.models import BankAccounts, Transaction
from core_app.functions import fixQuotesForCSV, convertToInt, buildTagDict, prepareDataFrame, prepare_table,\
    check_other_records, add_tags_to_database, add_df_to_account, populate_universal_tags, first_run, get_comparison, \
    prepare_list_for_dropdown


from .models import Transaction, Tags, UniversalTags

# _______________________main pages ________________________________________
def home(request):
    message = 'Hello and welcome to Evergreen Financial!'
    template = loader.get_template('core_app/index.html')
    # populate_universal_tags() #only run this the first time.  It populates the database
    context = {
        'user':request.user,
        'message':message
    }
    return HttpResponse(template.render(context, request))

def main_page(request):

    if request.user.is_authenticated:
        template = loader.get_template('core_app/main.html')

        # _______________________preparing lists for dropdowns for forms ____________________________
        years = Transaction.objects.values_list('year', flat=True).filter(user=request.user).distinct()
        year_list = prepare_list_for_dropdown(years)

        months = Transaction.objects.values_list('monthNum', flat=True).filter(user=request.user).distinct()
        month_list = prepare_list_for_dropdown(months)

        categories = Transaction.objects.values_list('category', flat=True).filter(user=request.user).distinct()
        cat_list = []
        for cat in categories:
            if cat != None:
                if cat != 'Income':
                    cat_list.append((cat, cat))
        cat_list.sort()
        cat_list = [('All', 'All')] + cat_list

        income_categories = Transaction.objects.values_list('category', flat=True).filter(user=request.user).distinct()
        income_cat_list = []
        for cat in income_categories:
            if cat == 'Income':
                income_cat_list.append((cat, cat))
        income_cat_list.sort()
        income_cat_list = [('All', 'All')] + income_cat_list
        # __________________ end of dropdown preperations __________________________________________________________

        yearForm = YearForm(years=year_list)
        monthForm = MonthForm(monthNum=month_list)
        catForm = CategorySelection(categories=cat_list)
        incomeForm = IncomeCategorySelection(income_categories=income_cat_list)

        # ___________________________getting values for comparing expenses to previous years___________________________


        context = {
            'yearForm':yearForm,
            'monthForm':monthForm,
            'catForm':catForm,
            'incomeCatForm':incomeForm,
            'year_title':request.session['year']
        }
        return HttpResponse(template.render(context, request))
    else:
        return redirect('home')

def newAccount(request):
    if request.user.is_authenticated:
        if request.method == 'POST':
            form = UploadFileForm(request.POST, request.FILES)
            if form.is_valid():
                request.session['df'] = fixQuotesForCSV(request.FILES['file'])
                return redirect('account_details')
        else:
            form = UploadFileForm()
        return render(request, 'core_app/new_account.html', {'form': form})
    else:
        return redirect('home')

# lets the user choose the layout of the uploaded file and sets the proper columns then adds them to the database
def account_details(request):
    if request.user.is_authenticated:
        dataframe = request.session.get('df', None)
        dataframe = pd.read_json(dataframe)
        dataframe = dataframe.reset_index(drop=True)
        df = dataframe.head(10).values.tolist()
        html = dataframe.head(10).to_html()

        # this is done to populate the dropdown menu for the forms
        tempCol = range(0, len(df[0]))
        columnNum = []
        for i in tempCol:
            j = i
            columnNum.append((i, j))

        if request.method == 'POST':
            form = AccountSelectForm(columnNum, request.POST)
            if form.is_valid():
                # sets up users account
                userAccount = BankAccounts()
                userAccount.user = request.user
                userAccount.account_name = request.POST['name']
                userAccount.balance = convertToInt(request.POST['balance'])
                userAccount.startRow = int(request.POST['rows'])
                userAccount.transDateCol = int(request.POST['date'])
                userAccount.transCreditCol = int(request.POST['credit'])
                userAccount.transDebitCol = int(request.POST['debit'])
                userAccount.transDescriptionCol = request.POST['description']
                userAccount.save()
                credit = int(request.POST['credit'])
                debit = int(request.POST['debit'])
                my_date = int(request.POST['date'])
                description = int(request.POST['description'])

                t = threading.Thread(target=add_df_to_account, kwargs={'dataframe': dataframe,
                                                                        'request': request,
                                                                        'userAccount': userAccount,
                                                                        'dateLocation':my_date,
                                                                       'creditLocation':credit,
                                                                       'debitLocation':debit,
                                                                       'descripLocation':description})
                t.start()
                # records_added = add_df_to_account(dataframe, request, userAccount, my_date, credit, debit, description)
                t1 = threading.Thread(target=first_run, kwargs={'user':request.user,
                                                                'account_name': userAccount.account_name})
                t1.start()
                template = loader.get_template('core_app/index.html')
                context = {
                    'user': request.user,
                }
                return HttpResponse(template.render(context, request))

        form = AccountSelectForm(columnNum)

        template = loader.get_template('core_app/account_details.html')
        context = {
            'form':form,
            'df':df,
            'html':html
        }
        return HttpResponse(template.render(context, request))
    else:
        return redirect('home')

# upload transactions to existing account
def upload_transactions(request):
    if request.user.is_authenticated:
        if request.method == 'POST':
            print('uploading transactions')
            form = UploadFileForm(request.POST, request.FILES)
            if form.is_valid():
                userAccount = request._post['accountNames']
                df = fixQuotesForCSV(request.FILES['file']) #fixes problems with quotes and apostrophes
                dataframe = pd.read_json(df)
                dataframe = dataframe.reset_index(drop=True)
                account = BankAccounts.objects.filter(account_name=userAccount, user=request.user).first() #gets user account named in the request

                t = threading.Thread(target=add_df_to_account, args=(dataframe, request, account, account.transDateCol,     # sends the dataframe to have the records added to the database
                                                  account.transCreditCol, account.transDebitCol, account.transDescriptionCol))
                t.start()
                t1 = threading.Thread(target=first_run, kwargs={'user':request.user,
                                                                'account_name': account.account_name})
                t1.start()

                message = 'Your records were added to the database.  We are working on processing them now'

                template = loader.get_template('core_app/index.html')
                context = {
                    'user': request.user,
                    'message': message,
                }
                return HttpResponse(template.render(context, request))

        template = loader.get_template('core_app/upload_transactions.html')
        accounts = BankAccounts.objects.values_list('account_name', flat=True).filter(user=request.user).distinct()
        account_list = []
        for account in accounts:
            account_list.append((account, account))  # have to pass a tuple to the select form for choices
        form = UploadToExistingAccount(accountNames=account_list)
        context = {
            'form': form,
        }
        return HttpResponse(template.render(context, request))
    else:
        return redirect('home')

def tags(request):
    if request.user.is_authenticated:
        if request.method == "POST":
            form_dict = request._post
            tagDict = buildTagDict(form_dict)

            for transNum, values in tagDict.items():
                print('new loop in tags')
                temp_record = Transaction.objects.get(id=transNum)
                temp_record.tag = values['tag']
                temp_record.category = values['cat']
                temp_record.year = temp_record.date.year
                temp_record.monthNum = temp_record.date.month
                temp_record.monthName = temp_record.date.strftime("%b")
                temp_record.save()

                t = threading.Thread(target=check_other_records, kwargs={'description': temp_record.description,
                                                                         'category':temp_record.category,
                                                                         'tag':temp_record.tag})
                t.start()

                add_tags_to_database(temp_record.category, temp_record.tag, request.user)
            return redirect('tags')


        trans = Transaction.objects.all().filter(user=request.user, tag=None)[:20] #gets twenty records
        cats = Tags.objects.distinct().values_list('category', flat=True)
        tempcats = UniversalTags.objects.distinct().values_list('category', flat=True)
        cats1 = list(cats)
        tempcats1 = list(tempcats)
        cats1 += tempcats1
        cats1.sort()
        myset = set(cats1) #gets unique values
        cats1 = list(myset)

        tableList=[]
        for i in trans:
            temp_list = [i.id, i.date, i.description, float(i.credit)/100, float(i.debit)/100]
            tableList.append(temp_list)

        template = loader.get_template('core_app/tags.html')
        context = {
            'tableList' : tableList,
            'category' : cats1
        }
        return HttpResponse(template.render(context, request))
    else:
        message = 'Please login first!'
        template = loader.get_template('core_app/index.html')
        context = {
            'user': request.user,
            'message': message
        }
        return HttpResponse(template.render(context, request))

def get_tag(request):
    if request.user.is_authenticated:
        category = request._post['category']
        number = request._post['number']
        number = number.replace('cat', '#tag_option')

        userTagsQuery = Tags.objects.filter(category=category)
        uniTagQuery = UniversalTags.objects.filter(category=category)
        temp_list = []
        for item in userTagsQuery:
            if item.tag not in temp_list:
                temp_list.append(item.tag)
        for item in uniTagQuery:
            if item.tag not in temp_list:
                temp_list.append(item.tag)
        temp_list.sort()
        result = {'tags': temp_list, 'number':number}

        return JsonResponse(result)

# ________________Chart Ajax request _______________________________

def get_months(request):
    if request.user.is_authenticated:
        request_year = request._post['year']
        if request_year == 'All':
            months = Transaction.objects.values_list('monthNum', flat=True).filter(user=request.user).distinct().order_by('monthNum')
        else:
            months = Transaction.objects.values_list('monthNum', flat=True).filter(user=request.user, year=request_year).distinct().order_by('monthNum')
        month_list = ['All']
        for month in months:
            month_list.append(month)
        return JsonResponse(month_list, safe=False)

def transaction_processing(myTransactions, my_interval):
    df = read_frame(myTransactions)
    df = prepareDataFrame(df)
    result = prepare_table(df, my_interval)
    return result

def first_chart(request):
    if request.user.is_authenticated:
        myTransactions = Transaction.objects.filter(user=request.user, exclude_value=False).all()
        result = transaction_processing(myTransactions, 'year')
        request.session['year'] = 'All'
        request.session['monthNum'] = '0'
        return JsonResponse(result, safe=False)

def new_chart_data(request):
    if request.user.is_authenticated:
       if request._post['name'] == 'years':
           if request._post['value'] == 'All':
               request.session['year'] = request._post['value']
               myTransactions = Transaction.objects.filter(user=request.user, exclude_value=False).all()
               result = transaction_processing(myTransactions, 'year') #this is added to change the title of the charts
               result['session_title'] = 'All Years'
               return JsonResponse(result)
           else:
               request.session['year'] = request._post['value']
               myTransactions = Transaction.objects.filter(user=request.user, year=int(request._post['value']), exclude_value=False).all()
               result = transaction_processing(myTransactions, 'monthNum')
               result['session_title'] = request.session['year'] #this is added to change the title of the charts
               return JsonResponse(result)

       if request._post['name'] == 'monthNum':
           if request._post['value'] == '0':
               request.session['monthNum'] = '0'
               myTransactions = Transaction.objects.filter(user=request.user, year=int(request.session['year']), exclude_value=False).all()
               result = transaction_processing(myTransactions, 'monthNum')
               result['session_title'] = request.session['year'] #this is added to change the title of the charts
               return JsonResponse(result)
           else:
               request.session['monthNum'] = request._post['value']
               myTransactions = Transaction.objects.filter(user=request.user, monthNum=int(request._post['value']), year=int(request.session['year']), exclude_value=False).all()
               result = transaction_processing(myTransactions, 'day')
               result['session_title'] = '{} {}'.format(request.session['monthNum'], request.session['year']) #this is added to change the title of the charts
               return JsonResponse(result)

def new_tag_data(request):
    if request.user.is_authenticated:
        request_cat = request._post['value']
        if request.session['year'] == 'All':
            tags = Transaction.objects.filter(user=request.user, category=request_cat,).all()
        elif request.session['monthNum'] == '0':
            tags = Transaction.objects.filter(user=request.user, category=request_cat, year=int(request.session['year']),
                                              ).all()
        else:
            tags = Transaction.objects.filter(user=request.user, category=request_cat,
                                              year=int(request.session['year']),monthNum = int(request.session['monthNum'])
                                              ).all()


        df = read_frame(tags)
        df = prepareDataFrame(df)

        # tag chart
        tag_list = df.tag.unique()
        tag_dict = {}
        tag_labels = []
        for tag in tag_list:
            result = df.loc[df['tag'] == tag, 'debit'].sum()
            result = result * -1  # this is put in so the chart shows posative values.  It didn't like negative ones
            if result > 0:
                tag_dict[tag] = result
                tag_labels.append(str(tag))

        results = {
            'tag_labels': tag_labels,
            'tag_vals': tag_dict,
        }
        return JsonResponse(results, safe=False)

def new_income_tag_data(request):
    if request.user.is_authenticated:
        request_cat = request._post['value']
        if request.session['year'] == 'All':
            tags = Transaction.objects.filter(user=request.user, category=request_cat, ).all()
        elif request.session['monthNum'] == '0':
            tags = Transaction.objects.filter(user=request.user, category=request_cat,
                                              year=int(request.session['year']),
                                              ).all()
        else:
            tags = Transaction.objects.filter(user=request.user, category=request_cat,
                                              year=int(request.session['year']),
                                              monthNum=int(request.session['monthNum'])
                                              ).all()

        df = read_frame(tags)
        df = prepareDataFrame(df)

        # income tag chart
        tag_list = df.tag.unique()
        tag_dict = {}
        tag_labels = []
        for tag in tag_list:
            result = df.loc[df['tag'] == tag, 'credit'].sum()
            if result > 0:
                tag_dict[tag] = result
                tag_labels.append(str(tag))

        results = {
            'income_tag_labels': tag_labels,
            'income_tag_vals': tag_dict,
        }
        return JsonResponse(results, safe=False)

def update_cat_dropdown(request):
    if request.user.is_authenticated:
        year = request.session['year']
        month = request.session['monthNum']
        if year == 'All':
            tags = Transaction.objects.filter(user=request.user).all()
        elif request.session['monthNum'] == '0':
            tags = Transaction.objects.filter(user=request.user, year=int(request.session['year']),).all()
        else:
            tags = Transaction.objects.filter(user=request.user, year=int(request.session['year']),
                                              monthNum=int(request.session['monthNum'])).all()

        df = read_frame(tags)
        df = prepareDataFrame(df)

        # income tag chart
        cat_list = df.category.unique()
        debit_labels = []
        credit_labels = []
        for cat in cat_list:
            credit = df.loc[df['category'] == cat, 'credit'].sum()
            debit = df.loc[df['category'] == cat, 'debit'].sum()
            debit = debit * -1
            if credit > 0:
                credit_labels.append(str(cat))
            if debit > 0:
                debit_labels.append(str(cat))
        debit_labels.sort()
        credit_labels.sort()
        debit_labels = ['All'] + debit_labels
        credit_labels = ['All'] + credit_labels



        results = {
            'debit': debit_labels,
            'credit': credit_labels,
        }
        return JsonResponse(results, safe=False)

# __________________Generic Pages______________________________
def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            print('login successful')
            return redirect('main_page')
    else:
        form = UserCreationForm()
    return render(request, 'core_app/signup.html', {'form': form})

def contact(request):
    form_class = ContactForm

    if request.method == 'POST':
        form = form_class(data=request.POST)

        if form.is_valid():
            contact_name = request.POST.get('contact_name', '')
            contact_email = request.POST.get('contact_email', '')
            form_content = request.POST.get('content', '')

            # Email the profile with the
            # contact information

        ctx = {
            'contact_name': contact_name,
            'contact_email': contact_email,
            'form_content': form_content,
        }
        message = loader.render_to_string('core_app/contact_template.html', ctx)
        msg = EmailMessage("New contact form submission", form_content, headers = {'Reply-To': contact_email }, to=['info@carcostcalculator.ca'])
        msg.content_subtype = 'html'
        msg.send()
        return redirect('contact')


    return render(request, 'core_app/contact.html', {
        'form': form_class,
    })

def handler404(request):
    template = loader.get_template('core_app/404.html')
    context = {}
    return HttpResponse(template.render(context, request))

def handler500(request, template_name='404.html'):
    template = loader.get_template('core_app/500.html')
    context ={}
    return HttpResponse(template.render(context, request))

