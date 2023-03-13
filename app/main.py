from flask import Flask, request, render_template
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import regex as re

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    
    def process_df(df):
        df.columns = [col.strip() for col in df.columns]
        df['fasting'] = (df['event'] == ' Fasting[8]').astype(int)
        # only with memo or fasting
        df = df.loc[~pd.isnull(df['memo']) | (df['fasting'] == 1)]
        # only bev
        df = df.loc[~df['memo'].apply(lambda x: ((str(x).lower().find('joakim') > -1) or \
                                                 (str(x).lower().startswith('ann')) or \
                                                 (str(x).lower().startswith('christina'))
                                                ))]
        # format dates
        weekDaysMapping = ("Monday", "Tuesday",
                           "Wednesday", "Thursday",
                           "Friday", "Saturday",
                           "Sunday")
        df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
        df['date'] = pd.to_datetime(df['date']).apply(lambda x: x.date())
        df['weekday'] = df['date'].apply(lambda x: weekDaysMapping[x.weekday()])
        df.sort_values(['date', 'time'], inplace=True)
        dates = sorted(df['date'].unique())
        # parse time
        def parse_time(x):
            if pd.isnull(x):
                return 0
            pat = r'([\D]*)(([\d \.]*)(?=hour))?([\D]*)(([\d \.]*)(?=min))?'
            p = re.compile(pat, re.IGNORECASE)
            result = re.search(p, x)
            try:
                h = float(result.group(2).strip())
            except:
                h = 0
            try:
                m = float(result.group(5).strip())
            except:
                m = 0
            t = 60 * h + m
            return t
        df['minutes'] = df['memo'].apply(parse_time)
        df['diff_1'] = abs(df['minutes'] - 60)
        
        df['meal_timestamp'] = df.apply(lambda x: x['timestamp'] - timedelta(minutes = x['minutes']), axis=1)
        df['hour'] = df['meal_timestamp'].apply(lambda x: x.hour)
        df['meal_date'] = df['meal_timestamp'].apply(lambda x: x.date())
        
        def classify_meal(x):
            if x['fasting'] == 1:
                return 'fasting'
            for meal in ('snack', 'breakfast', 'lunch', 'dinner'):
                if str(x['memo']).lower().find(meal) > -1:
                    return meal 
            if x['hour'] >= 5 and x['hour'] < 11:
                return 'breakfast'
            if x['hour'] >= 11 and x['hour'] < 15:
                return 'lunch'
            if x['hour'] >= 18 and x['hour'] < 23:
                return 'dinner'
            return 'snack'
        df['meal_class'] = df.apply(classify_meal, axis=1)
        
        def extract_glucose(x, meal_class):
            c = x.loc[x['meal_class'] == meal_class]
            if len(c) == 0:
                return (np.nan, '')
            res = c.sort_values('diff_1').iloc[0]
            return (res['memo'], res['glucose(mg/dL)'])
        
        def extract_date(date):
            x = df.loc[df['meal_date'] == date].sort_values('meal_timestamp')
            d = [extract_glucose(x, meal_class) for meal_class in ('fasting', 'breakfast', 'lunch', 'dinner')]
            return [str(date), weekDaysMapping[date.weekday()]] + [d[n][1] for n in range(4)] + [d[n][0] for n in range(1, 4)]
        
        out = pd.DataFrame([extract_date(date) for date in df['date'].unique()],
                           columns = ['Date', 'Day', 'Fasting', 'Breakfast', 'Lunch', 'Dinner', 'Breakfast', 'Lunch', 'Dinner']
                          )
        return out.fillna('')
     
    def make_table(trs):
        res = '''
         <table border="1" class="dataframe">
           <thead>
             <tr style="text-align: right;">
               <th></th>
               <th></th>
               <th colspan ="4">Blood Sugar Records</th>
               <th colspan ="3">Food Records</th>
             </tr>
             <tr style="text-align: right;">
               <th>Date</th>
               <th>Day</th>
               <th>Fasting</th>
               <th>Breakfast</th>
               <th>Lunch</th>
               <th>Dinner</th>
               <th>Breakfast</th>
               <th>Lunch</th>
               <th>Dinner</th>
             </tr>
           </thead>
           <tbody>
       {trs}
           </tbody>
         </table>'''.format(trs=trs)
        return res
    
    def tag_bad(x, th=140):
        try:
            return " class=high " if int(x) > th else ""
        except:
            return ""
    def add_day(row):
        tr = '''  <tr>
         <td>{0}</td>
         <td>{1}</td>
         <td {9}>{2}</td>
         <td {10}>{3}</td>
         <td {11}>{4}</td>
         <td {12}>{5}</td>
         <td>{6}</td>
         <td>{7}</td>
         <td>{8}</td>
       </tr>'''.format(row.iloc[0],
                       row.iloc[1],
                       row.iloc[2],
                       row.iloc[3],
                       row.iloc[4],
                       row.iloc[5],
                       row.iloc[6],
                       row.iloc[7],
                       row.iloc[8],
                       tag_bad(row.iloc[2], 95),
                       tag_bad(row.iloc[3], 140),
                       tag_bad(row.iloc[4], 140),
                       tag_bad(row.iloc[5], 140)
                       )
        return tr  
        
    if request.method == 'POST':
        df = pd.read_csv(request.files.get('file'), header=2)
        df = process_df(df)
        trs = '\n'.join([add_day(row) for _, row in df.iterrows()])
        tab = make_table(trs)        
        return render_template('index.html', tab=tab)
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)