import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe
import locale
from datetime import datetime

# Устанавливаем локаль для корректной обработки чисел
try:
    locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')
except locale.Error:
    locale.setlocale(locale.LC_ALL, '')

# Настройки
SHEET_ID = "12vLykJcM1y_mO8yFcrk8sqXcDa915vH1UbrrKYvncFk"
WORKSHEET_NAME = "test"
DEFAULT_PEOPLE = ["Иха", "Влад", "Локи"]

# Авторизация
@st.cache_resource
def connect_to_gsheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    return gspread.authorize(credentials)

def safe_float(value):
    """Конвертирует значение в float, поддерживая запятую и точку как десятичный разделитель"""
    if value in [None, "", " "]:
        return 0.0
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Удаляем пробелы и заменяем запятую на точку
            value = value.replace(',', '.').replace(' ', '')
            return float(value)
        return 0.0
    except (ValueError, TypeError) as e:
        st.warning(f"Ошибка преобразования числа '{value}': {str(e)}")
        return 0.0

def parse_date(value):
    """Конвертирует строку даты в объект datetime, поддерживая национальные форматы"""
    if value in [None, "", " "]:
        return None
    try:
        return pd.to_datetime(value, dayfirst=True)
    except (ValueError, TypeError):
        return None

def get_sheet_data():
    try:
        client = connect_to_gsheet()
        sheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)
        data = sheet.get_all_records()
        
        # Конвертируем данные в правильные типы
        processed_data = []
        for row in data:
            processed_row = {
                "Кто платил": str(row.get("Кто платил", "")),
                "Описание трат": str(row.get("Описание трат", "")),
                "Сумма чека": safe_float(row.get("Сумма чека", 0)),
                "Дата": parse_date(row.get("Дата", "")),
                **{p: int(row.get(p, 0)) if row.get(p, 0) in [1, 0] else 0 
                   for p in DEFAULT_PEOPLE}
            }
            processed_data.append(processed_row)
            
        df = pd.DataFrame(processed_data)
        # Отладочный вывод
        #st.write("Загруженные данные из Google Sheets:", df)
        return df, sheet
    except Exception as e:
        st.error(f"Ошибка загрузки: {str(e)}")
        return pd.DataFrame(columns=["Кто платил", "Описание трат", "Сумма чека", "Дата"] + DEFAULT_PEOPLE), None

def update_sheet(sheet, df):
    if sheet is None:
        return
    try:
        # Преобразуем числа и даты для сохранения в Google Sheets
        df_to_save = df.copy()
        if 'Сумма чека' in df_to_save.columns:
            df_to_save['Сумма чека'] = df_to_save['Сумма чека'].apply(
                lambda x: f"{x:.2f}" if pd.notnull(x) else '0.00'
            )
        if 'Дата' in df_to_save.columns:
            df_to_save['Дата'] = df_to_save['Дата'].apply(
                lambda x: x.strftime('%d.%m.%Y') if pd.notnull(x) else ''
            )
        # Отладочный вывод
        #st.write("Данные для сохранения в Google Sheets:", df_to_save)
        sheet.clear()
        set_with_dataframe(sheet, df_to_save)
    except Exception as e:
        st.error(f"Ошибка сохранения: {str(e)}")

def calculate_debts(df):
    if df.empty:
        return pd.DataFrame(columns=["Участник", "Баланс"])
    
    total_spent = {p: 0.0 for p in DEFAULT_PEOPLE}
    total_share = {p: 0.0 for p in DEFAULT_PEOPLE}
    
    for _, row in df.iterrows():
        payer = str(row.get("Кто платил", ""))
        if payer not in DEFAULT_PEOPLE:
            continue
            
        amount = safe_float(row.get("Сумма чека", 0))
        total_spent[payer] += amount
        
        participants = [p for p in DEFAULT_PEOPLE if int(row.get(p, 0)) == 1]
        if participants:
            share = amount / len(participants)
            for p in participants:
                total_share[p] += share
    
    balances = {p: round(total_spent[p] - total_share[p], 2) for p in DEFAULT_PEOPLE}
    return pd.DataFrame({
        "Участник": balances.keys(),
        "Баланс": balances.values()
    })

def main():
    st.title("🍽️ Калькулятор долгов")
    
    # Inject custom CSS for the "Добавить" buttons in forms
    st.markdown("""
        <style>
        /* Target only form submit buttons with label "Добавить" */
        div[data-testid="stForm"] button[kind="formSubmit"][aria-label="Добавить"] {
            background-color: #90EE90; /* Light green */
            color: black;
            width: 100%;
            padding: 10px;
            border: none;
            border-radius: 5px;
        }
        div[data-testid="stForm"] button[kind="formSubmit"][aria-label="Добавить"]:hover {
            background-color: #78DA78; /* Slightly darker green on hover */
            color: black;
        }
        </style>
    """, unsafe_allow_html=True)
    
    df, sheet = get_sheet_data()
    
    tab1, tab2, tab3 = st.tabs(["Добавить траты", "Управление", "Рассчёты"])
    
    with tab1:
        with st.form(key="expense_form", clear_on_submit=True):
            payer = st.selectbox("Кто оплатил", DEFAULT_PEOPLE)
            description = st.text_input("Описание")
            amount = st.number_input("Сумма", min_value=0.0, value=None, format="%.2f")
            date = st.date_input("Дата", value=datetime.today())
            
            st.write("Участники:")
            # Horizontal layout for checkboxes
            cols = st.columns(len(DEFAULT_PEOPLE))
            participants = {}
            for idx, person in enumerate(DEFAULT_PEOPLE):
                with cols[idx]:
                    participants[person] = st.checkbox(person, value=True, key=f"part_{person}")
            
            if st.form_submit_button("Добавить"):
                if not description:
                    st.error("Введите описание")
                else:
                    new_row = {
                        "Кто платил": payer,
                        "Описание трат": description,
                        "Сумма чека": safe_float(amount),
                        "Дата": date,
                        **{p: 1 if participants[p] else 0 for p in DEFAULT_PEOPLE}
                    }
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    update_sheet(sheet, df)
                    st.success("Добавлено!")
                    st.rerun()
        
        # Display balances below the form
        st.subheader("Текущий баланс")
        balances = calculate_debts(df)
        st.dataframe(balances)
    
    with tab2:
        if not df.empty:
            edited_df = st.data_editor(
                df,
                column_config={
                    "Кто платил": st.column_config.SelectboxColumn(options=DEFAULT_PEOPLE),
                    "Сумма чека": st.column_config.NumberColumn(format="%.2f"),
                    "Дата": st.column_config.DateColumn(format="DD.MM.YYYY"),
                    **{p: st.column_config.CheckboxColumn() for p in DEFAULT_PEOPLE}
                },
                num_rows="dynamic",
                key="editor"
            )
            
            if st.button("Сохранить изменения"):
                df = edited_df
                update_sheet(sheet, df)
                st.success("Сохранено!")
                st.rerun()
                
            balances = calculate_debts(df)
            st.dataframe(balances)
            
            # Расчет переводов
            debtors = balances[balances["Баланс"] < 0]
            creditors = balances[balances["Баланс"] > 0]
            
            transactions = []
            for _, creditor in creditors.iterrows():
                for _, debtor in debtors.iterrows():
                    amount = min(creditor["Баланс"], -debtor["Баланс"])
                    if amount > 1:
                        transactions.append({
                            "От": debtor["Участник"],
                            "Кому": creditor["Участник"],
                            "Сумма": round(amount, 2)
                        })
            
            if transactions:
                st.dataframe(pd.DataFrame(transactions))
            else:
                st.success("Баланс сведен")
        else:
            st.warning("Нет данных")
    
    with tab3:
        # Calculate balances and transactions
        balances = calculate_debts(df)
        debtors = balances[balances["Баланс"] < 0]
        creditors = balances[balances["Баланс"] > 0]
        transactions = []
        for _, creditor in creditors.iterrows():
            for _, debtor in debtors.iterrows():
                amount = min(creditor["Баланс"], -debtor["Баланс"])
                if amount > 1:
                    transactions.append({
                        "От": debtor["Участник"],
                        "Кому": creditor["Участник"],
                        "Сумма": round(amount, 2)
                    })
        
        # Payer selection
        payer = st.selectbox("Кто платил", DEFAULT_PEOPLE, key="settlement_payer")
        recipient = st.selectbox("Кому", DEFAULT_PEOPLE, key="settlement_recipient")
        
        # Button to fill the amount with the specific debt (outside the form)
        specific_debt = 0.0
        if payer != recipient:
            for transaction in transactions:
                if transaction["От"] == payer and transaction["Кому"] == recipient:
                    specific_debt = transaction["Сумма"]
                    break
        
        if st.button("Погасить весь долг"):
            st.session_state["settlement_amount"] = specific_debt
        
        with st.form(key="settlement_form", clear_on_submit=True):
            # Initialize amount with session state if it exists, otherwise None
            amount = st.number_input(
                "Сумма",
                min_value=0.0,
                value=st.session_state.get("settlement_amount", None),
                format="%.2f",
                key="settlement_amount"
            )
            date = st.date_input("Дата", value=datetime.today(), key="settlement_date")
            
            if st.form_submit_button("Добавить"):
                if payer == recipient:
                    st.error("Плательщик и получатель не могут быть одним и тем же лицом")
                else:
                    new_row = {
                        "Кто платил": payer,
                        "Описание трат": "рассчёт",
                        "Сумма чека": safe_float(amount),
                        "Дата": date,
                        **{p: 1 if p == recipient else 0 for p in DEFAULT_PEOPLE}
                    }
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    update_sheet(sheet, df)
                    st.success("Рассчёт добавлен!")
                    st.rerun()

if __name__ == "__main__":
    main()
