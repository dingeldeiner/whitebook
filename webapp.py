import streamlit as st
import mariadb
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from statsmodels.nonparametric.smoothers_lowess import lowess

st.set_page_config(page_title='whitebook', page_icon=':car:', layout="centered", initial_sidebar_state="expanded", menu_items=None)

#HIDE FULLSCREEN BUTTONS
hide_img_fs = '''
<style>
button[title="View fullscreen"]{
    visibility: hidden;
    right: 0rem;}
</style>
'''
st.markdown(hide_img_fs, unsafe_allow_html=True)

#TABS
tabs = st.tabs(['Explore', 'Appraise'])

#LOAD DATA
@st.cache_data
def loaddata(selectcolumns):
    query = 'SELECT ' + selectcolumns + ' FROM vehicles WHERE Date_Posted > 1675221580;'
    db = mariadb.connect(
        host=st.secrets.db_host,
        user=st.secrets.db_username,
        password=st.secrets.db_password,
        database=st.secrets.db_name,
    )
    df = (
        pd.read_sql(query, db)
        .replace({
            None:np.nan,
            'null':np.nan
        })
    )
    df['Date_Posted_S'] = df['Date_Posted']
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='s')
    df['Date_Posted'] = pd.to_datetime(df['Date_Posted'], unit='s')
    df['Time_On_Market'] = df['Timestamp'].sub(df['Date_Posted'])
    return df
    db.close()

data = loaddata('Price, Date_Posted, Year, Make, Model, Trim, Colour, Body_Type, Doors, Seats, Drivetrain, Transmission, Fuel_Type, Kilometers, Sold, Timestamp, Latitude, Longitude')
#exploredata = data.query("")

#FILTERS
def getFilterBy(df, col_name): #gets list of strings to filter by
    x = [g for g in list(df[col_name].unique()) if type(g) is str]
    x.sort()
    return x

mins = data[['Year','Kilometers','Price']].min(numeric_only=True)
maxes = data[['Year','Kilometers','Price']].max(numeric_only=True)

min_year = 1960
max_year = int(maxes.Year)
min_kilometers = 20000
max_kilometers = 300000
min_price = 1500
max_price = 100000

with st.sidebar:
    #TITLE
    st.header("Alberta Whitebook :chart_with_upwards_trend:")
    st.caption(":red[real-time used vehicle markets]")

    #FILTERS
    st.text("Filters")
    selections = []
    body_type = st.multiselect('Type:', getFilterBy(data, 'Body_Type'))
    selections.append(('Body_Type', body_type))
    make = st.multiselect('Make:', getFilterBy(data, 'Make'))
    selections.append(('Make', make))
    if len(make) == 1:
        model = st.multiselect('Model:', getFilterBy(data.query(f"Make == '{make[0]}'"), 'Model'))
        selections.append(('Model', model))
    drivetrain = st.multiselect('Drivetrain:', getFilterBy(data, 'Drivetrain'))
    selections.append(('Drivetrain', drivetrain))
    transmission = st.multiselect('Transmission:', getFilterBy(data, 'Transmission'))
    selections.append(('Transmission', transmission))
    fueltype = st.multiselect('Fuel Type:', getFilterBy(data, 'Fuel_Type'))
    selections.append(('Fuel_Type', fueltype))

    col1, col2 = st.columns([1,1])
    year = (
        col1.number_input(label='Year: (min)', step=1, value=min_year),
        col2.number_input(label='Year: (max)', step=1, value=max_year)
        )
    selections.append(('Year', year))
    kilometers = (
        col1.number_input(label='Kilometers: (min)', step=1, value=min_kilometers),
        col2.number_input('Kilometers: (max)', step=1, value=max_kilometers)
        )
    selections.append(('Kilometers', kilometers))
    price = (col1.number_input(label='Price: (min)', step=1, value=min_price),(col2.number_input(label='Price: (max)', step=1, value=max_price)))
    selections.append(('Price', price))


    args = []
    desc = []
    for col_name, selection in selections:
        if type(selection) == str and selection != 'All':
            args.append(f"{col_name} == '{selection}'")
            desc.append(selection)
        elif type(selection) == list and len(selection) > 0:
            args.append('('+' or '.join([f"{col_name} == '{x}'" for x in selection])+')')
            desc = desc + selection
        elif type(selection) == tuple:
            if type(selection[0]) == int:
                args.append(f"{col_name} >= {selection[0]}")
                desc.append(f"{col_name} > {selection[0]}")
            if type(selection[1]) == int:
                args.append(f"{col_name} <= {selection[1]}")
                desc.append(f"{col_name} < {selection[1]}")
    query = ' and '.join(args)
    data = data.query(query)
    st.text(f"{data.shape[0]} records found.")

#EXPLORE TAB
with tabs[0]:
    time_series = np.arange(
        start = data['Date_Posted_S'].min(),
        stop = data['Date_Posted_S'].max(),
        step = 3600 * 4 #interval of 4 hours
    )
    avg_price = lowess(
        endog = data['Price'],
        exog = data['Date_Posted_S'],
        frac = 0.2,
        it = 0,
        xvals = time_series,
        is_sorted = False,
        missing = 'drop',
        return_sorted = False
    )
    price_time_series = pd.Series(avg_price, index = pd.to_datetime(time_series, unit='s'))
    st.plotly_chart(
        px.line(
            price_time_series,
            title = 'Market Overview (Average Price vs Time)',
            labels = {
                'value':'Price',
                'index':'Time'
            },
            color_discrete_sequence = ['#ff6969']
        )
        .update_layout(
            showlegend = False
        ),
        config = {
            'staticPlot':True
        }
        ,
        use_container_width = True
    )
    
    mapdata = (
        data[['Latitude', 'Longitude']]
        .rename(columns={'Latitude':'lat', 'Longitude':'lon'})
        .query("lat > 48 and lat < 61 and lon > -121 and lon < -109")
    )
    st.map(mapdata)

#APPRAISE TAB
with tabs[1]:
    st.caption('Use filters in the sidebar to get info specific to your vehicle.')

    km_index = np.arange(
        start = data['Kilometers'].min(),
        stop = data['Kilometers'].max(),
        step = 5000
    )
    avg_price_by_km = lowess(
        endog = data['Price'],
        exog = data['Kilometers'],
        frac = 0.2,
        it = 0,
        xvals = km_index,
        is_sorted = False,
        missing = 'drop',
        return_sorted = False
    )
    price_km_series = pd.Series(avg_price_by_km, index = km_index)
    st.plotly_chart(
        px.line(
            price_km_series,
            title = 'Average Price By Mileage',
            labels = {
                'value':'Price',
                'index':'Kilometers'
            },
            color_discrete_sequence = ['#ff6969']
        )
        .update_layout(
            showlegend = False,
            xaxis_fixedrange = True,
            yaxis_fixedrange = True
        ),
        config = {
            'staticPlot':True
        },
        use_container_width = True
    )
