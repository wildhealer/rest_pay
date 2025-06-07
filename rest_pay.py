import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe

# Настройки
SHEET_ID = "1M2OrKITimaLlWAs3yTqchsESFNdUxitZnfQ65k4bIXI"
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
    """Конвертирует значение в float безопасно"""
    try:
        return float(value) if value not in [None, ""] else 0.0
    except (ValueError, TypeError):
        return 0.0

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
                **{p: int(row.get(p, 0)) if row.get(p, 0) in [1, 0] else 0 
                   for p in DEFAULT_PEOPLE}
            }
            processed_data.append(processed_row)
            
        return pd.DataFrame(processed_data), sheet
    except Exception as e:
        st.error(f"Ошибка загрузки: {str(e)}")
        return pd.DataFrame(columns=["Кто платил", "Описание трат", "Сумма чека"] + DEFAULT_PEOPLE), None

def update_sheet(sheet, df):
    if sheet is None:
        return
    try:
        sheet.clear()
        set_with_dataframe(sheet, df)
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
    
    df, sheet = get_sheet_data()
    
    tab1, tab2 = st.tabs(["Добавить траты", "Управление"])
    
    with tab1:
        with st.form(key="expense_form", clear_on_submit=True):
            payer = st.selectbox("Кто оплатил", DEFAULT_PEOPLE)
            description = st.text_input("Описание")
            amount = st.number_input("Сумма", min_value=0, value=1000)
            
            st.write("Участники:")
            participants = {p: st.checkbox(p, value=True, key=f"part_{p}") 
                          for p in DEFAULT_PEOPLE}
            
            if st.form_submit_button("Добавить"):
                if not description:
                    st.error("Введите описание")
                else:
                    new_row = {
                        "Кто платил": payer,
                        "Описание трат": description,
                        "Сумма чека": float(amount),
                        **{p: 1 if participants[p] else 0 for p in DEFAULT_PEOPLE}
                    }
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    update_sheet(sheet, df)
                    st.success("Добавлено!")
                    st.rerun()
    
    with tab2:
        if not df.empty:
            edited_df = st.data_editor(
                df,
                column_config={
                    "Кто платил": st.column_config.SelectboxColumn(options=DEFAULT_PEOPLE),
                    "Сумма чека": st.column_config.NumberColumn(format="%.2f"),
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

if __name__ == "__main__":
    main()
