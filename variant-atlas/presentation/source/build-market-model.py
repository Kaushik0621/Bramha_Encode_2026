from pathlib import Path
import json
import xlsxwriter
r=Path(__file__).resolve().parents[1]
model={
 'reviewed_on':'2026-10-25',
 'evidence':{'us_biotech_company_pool':{'reported':'more than 2,000','model_reference':2000,'publisher':'Biotechnology Innovation Organization (BIO)','source_url':'https://www.bio.org/sites/default/files/2026-01/the_power_of_small_and_mid-size_biotechs.pdf','page':1,'status':'industry-association estimate; rounded model reference, not qualified prospects'}},
 'customer_value_assumptions':{'applicable_investigations_per_month':8,'net_hours_recovered_per_investigation':2,'research_capacity_value_usd_per_hour':60,'lab_subscription_usd_per_month':300,'net_means':'after additional review, onboarding and correction effort; no measured time saving'},
 'opportunity_assumptions':{'geography':'United States','model_company_reference_pool':2000,'eligible_fit_rates':[.1,.2,.3],'paid_accounts_per_eligible_company':1,'lab_subscription_usd_per_month':300,'conversion_and_retention':'not measured; conditional full-coverage pool assumes 100%, not a revenue forecast','scope':'academics and other geographies excluded; current PTEN-only product may qualify far fewer firms'},
 'derived':{'customer_capacity_value_usd_year':11520,'fee_usd_year':3600,'capacity_value_after_fee_usd_year':7920,'capacity_value_to_fee_ratio':3.2,'breakeven_net_hours_month':5,'low_use_capacity_value_usd_year':2880,'subscription_pool_usd_year':[720000,1440000,2160000]},
 'gap_status':'A specific workflow gap hypothesis, not demonstrated unmet demand or a measured global TAM.',
 'competitor_sources':['https://www.benchling.com/academic','https://galaxyproject.org/','https://mavedb.org/docs/mavedb/mavemd/variant-page.html']}
assert 8*2*60*12==11520
assert all(2000*f*300*12==v for f,v in zip([.1,.2,.3],model['derived']['subscription_pool_usd_year']))
(r/'source/market-model.json').write_text(json.dumps(model,indent=2))
w=xlsxwriter.Workbook(r/'Market-Value-Model.xlsx')
head=w.add_format({'bold':True,'bg_color':'#193B3B','font_color':'#FFFDF8','font_size':13})
label=w.add_format({'text_wrap':True,'valign':'top'})
inputf=w.add_format({'font_color':'#1657A0','bg_color':'#E7EEF5','num_format':'#,##0.00'})
usd=w.add_format({'num_format':'$#,##0;($#,##0)'})
percent=w.add_format({'num_format':'0%','font_color':'#1657A0','bg_color':'#E7EEF5'})
result=w.add_format({'bold':True,'num_format':'$#,##0;($#,##0)','bg_color':'#E7EEE5'})
note=w.add_format({'text_wrap':True,'font_color':'#58706F','valign':'top'})
s=w.add_worksheet('Customer value');s.set_column('A:A',54);s.set_column('B:B',22);s.set_column('C:C',74);s.freeze_panes(2,0)
s.write_row('A1',['Customer capacity value — all inputs assumed','Value','Meaning'],head)
inputs=[('Cases per month',8,'Applicable investigation volume; not measured'),('Net hours recovered per case',2,'After review, onboarding and corrections; not measured'),('Research capacity value per hour (USD)',60,'Assumed loaded capacity rate, not a salary estimate'),('Lab fee per month (USD)',300,'Proposed price, not a commercial offer'),('Months per year',12,'Arithmetic constant')]
for row,(a,b,c) in enumerate(inputs,2):s.write(row,0,a,label);s.write_number(row,1,b,inputf);s.write(row,2,c,note)
for cell,lab,formula,value,fmt,desc in [
 ('B9','Annual capacity value','=B3*B4*B5*B7',11520,result,'Released capacity, not cash savings'),
 ('B10','Annual fee','=B6*B7',3600,usd,'Subscription fee only'),
 ('B11','Capacity value after fee','=B9-B10',7920,result,'Not profit; excludes any unmodelled costs'),
 ('B12','Capacity value / fee','=IFERROR(B9/B10,0)',3.2,None,'Benefit-to-fee ratio, not measured ROI'),
 ('B13','Break-even net hours per month','=IFERROR(B6/B5,0)',5,None,'Must recover this many net hours to cover the fee'),
 ('B15','Low-use case: 2 cases/month, annual value','=2*B4*B5*B7',2880,usd,'Below the proposed fee; no automatic positive value proposition')]:
 row=int(cell[1:])-1;s.write(row,0,lab,label);s.write_formula(cell,formula,fmt,value);s.write(row,2,desc,note)
s=w.add_worksheet('US opportunity');s.set_column('A:A',50);s.set_column('B:D',22);s.set_column('E:E',72);s.freeze_panes(2,0)
s.write_row('A1',['Conditional annual subscription pool','Low','Base','High','Qualification'],head)
for col,f in enumerate([.1,.2,.3],1):
 s.write_number(2,col,2000,inputf);s.write_number(3,col,f,percent);s.write_number(5,col,1,inputf);s.write_number(6,col,300,inputf);s.write_number(7,col,12,inputf)
 letter=chr(65+col)
 s.write_formula(4,col,f'={letter}3*{letter}4',None,2000*f)
 s.write_formula(8,col,f'={letter}5*{letter}6*{letter}7*{letter}8',result,2000*f*3600)
 s.write_number(10,col,.1,percent)
 s.write_formula(11,col,f'={letter}9*{letter}11',usd,2000*f*360)
for row,lab in [(2,'Rounded US biotech reference pool'),(3,'Assumed eligible fit rate'),(4,'Hypothetical eligible companies'),(5,'Paid accounts per eligible company'),(6,'Proposed monthly fee (USD)'),(7,'Months per year'),(8,'Conditional annual subscription pool'),(10,'Illustrative effective uptake fraction'),(11,'Revenue at illustrative uptake')]:s.write(row,0,lab,label)
s.write('E3','BIO says more than 2,000; not a buyer list.',note);s.write('E4','Unvalidated assumption; current PTEN scope may fit far fewer.',note);s.write('E9','Full eligible coverage, not TAM or forecast revenue. Excludes academia and non-US firms.',note);s.write('E12','Uptake is assumed, not a pipeline or forecast. Accounts, conversion and retention require evidence.',note)
s.write('A15','First 20 accounts: annualized subscriptions',label);s.write_formula('B15','=20*B7*B8',result,72000)
s=w.add_worksheet('Sources and limits');s.set_column('A:A',35);s.set_column('B:B',115)
s.write_row('A1',['Evidence / assumption','Source or boundary'],head)
for i,(a,b) in enumerate([('Company reference pool',model['evidence']['us_biotech_company_pool']['source_url']),('Benchling academic offer','https://www.benchling.com/academic'),('Galaxy workflow scope','https://galaxyproject.org/'),('MaveDB interpretation scope','https://mavedb.org/docs/mavedb/mavemd/variant-page.html'),('Checked','25 October 2026'),('Value inputs','All time, volume, hourly rate, fit and price inputs are hypotheses. No measured savings or confirmed demand.'),('Commercial scope','US entry segment only; source pool includes firms that may never be relevant. Global TAM is not established.'),('Scientific scope','Computational research prototype; no monetized claim about avoiding failed experiments or improving clinical outcomes.')],1):s.write(i,0,a,label);s.write(i,1,b,note);s.set_row(i,42)
w.close()
print('Built editable customer-value and market-opportunity workbook; arithmetic checks passed.')
