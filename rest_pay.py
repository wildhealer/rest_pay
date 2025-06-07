import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe

# Настройки Google Sheets
SHEET_ID = "12vLykJcM1y_mO8yFcrk8sqXcDa915vH1UbrrKYvncFk"
WORKSHEET_NAME = "test"

# Авторизация в Google Sheets
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
    client = gspread.authorize(credentials)
    return client

def get_sheet_data():
    client = connect_to_gsheet()
    sheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)
    
    try:
        expected_headers = ["Кто платил", "Описание трат", "Сумма чека", "Иха", "Влад", "Локи"]
        data = sheet.get_all_records(expected_headers=expected_headers)
        return pd.DataFrame(data), sheet
    except Exception as e:
        st.error(f"Ошибка загрузки: {e}")
        return pd.DataFrame(columns=expected_headers), sheet

def update_sheet(sheet, df):
    sheet.clear()
    set_with_dataframe(sheet, df)

def calculate_debts(df):
    if df.empty or 'Иха' not in df.columns:
        return pd.DataFrame()
    
    total_spent = {'Иха': 0, 'Влад': 0, 'Локи': 0}
    total_share = {'Иха': 0, 'Влад': 0, 'Локи': 0}
    
    for _, row in df.iterrows():
        payer = row['Кто платил']
        total_spent[payer] += row['Сумма чека']
        
        participants = [p for p in ['Иха', 'Влад', 'Локи'] if row[p] == 1]
        if participants:
            share = row['Сумма чека'] / len(participants)
            for p in participants:
                total_share[p] += share
    
    balances = {p: total_spent[p] - total_share[p] for p in ['Иха', 'Влад', 'Локи']}
    return pd.DataFrame({
        'Участник': balances.keys(),
        'Баланс': [round(b, 2) for b in balances.values()]
    })

def main():
    st.title("🍽️ Калькулятор долгов")
    
    # Загрузка данных
    df, sheet = get_sheet_data()
    
    # Управление участниками
    st.sidebar.header("Участники")
    if st.sidebar.button("Сбросить к стандартным"):
        st.session_state.people = ["Иха", "Влад", "Локи"]
    
    # Основное содержимое
    tab1, tab2 = st.tabs(["Добавить траты", "Управление тратами"])
    
    with tab1:
        with st.form(key="expense_form", clear_on_submit=True):
            st.header("Новая трата")
            
            payer = st.selectbox("Кто оплатил", ["Иха", "Влад", "Локи"])
            description = st.text_input("Описание")
            amount = st.number_input("Сумма", min_value=1, value=1000)
            
            st.write("Участники:")
            cols = st.columns(3)
            participants = {}
            for i, person in enumerate(["Иха", "Влад", "Локи"]):
                with cols[i]:
                    participants[person] = st.checkbox(person, value=True, key=f"part_{i}")
            
            submitted = st.form_submit_button("Добавить трату")
            
            if submitted:
                if not description:
                    st.error("Введите описание")
                else:
                    new_row = {
                        "Кто платил": payer,
                        "Описание трат": description,
                        "Сумма чека": amount,
                        **{p: 1 if participants[p] else 0 for p in ["Иха", "Влад", "Локи"]}
                    }
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    update_sheet(sheet, df)
                    st.success("Добавлено!")
                    st.rerun()
    
    with tab2:
        st.header("Управление тратами")
        
        if not df.empty:
            # Отображение с возможностью выбора для удаления
            edited_df = st.data_editor(
                df,
                column_config={
                    "Кто платил": st.column_config.SelectboxColumn(
                        "Кто платил",
                        options=["Иха", "Влад", "Локи"]
                    ),
                    "Сумма чека": st.column_config.NumberColumn(
                        "Сумма",
                        min_value=0
                    )
                },
                num_rows="dynamic",
                key="data_editor"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Сохранить изменения"):
                    update_sheet(sheet, edited_df)
                    st.success("Сохранено!")
                    st.rerun()
            
            with col2:
                if st.button("Удалить выбранные", type="primary"):
                    if len(st.session_state.data_editor["deleted_rows"]) > 0:
                        df = df.drop(st.session_state.data_editor["deleted_rows"])
                        update_sheet(sheet, df)
                        st.success("Удалено!")
                        st.rerun()
                    else:
                        st.warning("Выберите строки для удаления")
            
            # Расчет долгов
            st.header("Баланс участников")
            balances = calculate_debts(df)
            if not balances.empty:
                st.dataframe(balances)
                
                # Расчет переводов
                st.header("Рекомендуемые переводы")
                debtors = balances[balances['Баланс'] < 0]
                creditors = balances[balances['Баланс'] > 0]
                
                transactions = []
                for _, creditor in creditors.iterrows():
                    for _, debtor in debtors.iterrows():
                        amount = min(creditor['Баланс'], -debtor['Баланс'])
                        if amount > 1:
                            transactions.append({
                                "От": debtor['Участник'],
                                "Кому": creditor['Участник'],
                                "Сумма": round(amount, 2)
                            })
                
                if transactions:
                    st.dataframe(pd.DataFrame(transactions))
                else:
                    st.success("Баланс сведен, переводы не требуются")
        else:
            st.warning("Нет данных о тратах")

if __name__ == "__main__":
    main()
