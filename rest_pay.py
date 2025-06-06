import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe

# Настройки Google Sheets
SHEET_ID = "1M2OrKITimaLlWAs3yTqchsESFNdUxitZnfQ65k4bIXI"
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
    
    # Обработка данных с проверкой заголовков
    try:
        expected_headers = ["Кто платил", "Описание трат", "Сумма чека", "Иха", "Влад", "Локи"]
        data = sheet.get_all_records(expected_headers=expected_headers)
        return pd.DataFrame(data), sheet
    except Exception as e:
        st.error(f"Ошибка загрузки данных: {e}")
        return pd.DataFrame(columns=expected_headers), sheet

def update_sheet(sheet, df):
    sheet.clear()
    set_with_dataframe(sheet, df)

def calculate_debts():
    st.title("🍽️ Калькулятор долгов с синхронизацией Google Sheets")
    
    # Инициализация данных
    if 'people' not in st.session_state:
        st.session_state.people = ["Иха", "Влад", "Локи"]
    
    # Загрузка данных
    try:
        df, sheet = get_sheet_data()
    except Exception as e:
        st.error(f"Ошибка: {str(e)}")
        df = pd.DataFrame(columns=["Кто платил", "Описание трат", "Сумма чека"] + st.session_state.people)
        sheet = None

    # Управление участниками
    st.header("1. Участники")
    col1, col2 = st.columns(2)
    
    with col1:
        new_person = st.text_input("Добавить участника", key="new_person_input")
        if st.button("Добавить", key="add_person_btn"):
            if new_person and new_person not in st.session_state.people:
                st.session_state.people.append(new_person)
                st.rerun()
    
    with col2:
        if st.session_state.people:
            to_remove = st.selectbox(
                "Выберите участника для удаления", 
                st.session_state.people,
                key="remove_person_select"
            )
            if st.button("Удалить", key="remove_person_btn"):
                st.session_state.people.remove(to_remove)
                st.rerun()

    st.write("Текущие участники:", ", ".join(st.session_state.people))

    # Форма добавления трат
    st.header("2. Добавление трат")
    with st.form("expense_form", clear_on_submit=True):
        payer = st.selectbox(
            "Кто оплатил", 
            st.session_state.people,
            key="payer_select"
        )
        description = st.text_input(
            "Описание трат (место/ресторан)", 
            key="description_input"
        )
        amount = st.number_input(
            "Сумма чека", 
            min_value=1, 
            value=1000,
            key="amount_input"
        )
        
        st.write("Кто участвовал:")
        participants = {}
        cols = st.columns(3)
        for i, person in enumerate(st.session_state.people):
            with cols[i % 3]:
                participants[person] = st.checkbox(
                    person, 
                    value=True, 
                    key=f"participant_{person}_{i}"
                )
        
        submitted = st.form_submit_button(
            "Добавить трату", 
            key="submit_expense_btn"
        )
        
        if submitted:
            if not description:
                st.error("Введите описание трат")
            elif amount <= 0:
                st.error("Сумма должна быть положительной")
            else:
                new_row = {
                    "Кто платил": payer,
                    "Описание трат": description,
                    "Сумма чека": amount,
                    **{p: 1 if participants[p] else 0 for p in st.session_state.people}
                }
                
                try:
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    if sheet:
                        update_sheet(sheet, df)
                    st.success("Трата добавлена!")
                except Exception as e:
                    st.error(f"Ошибка сохранения: {str(e)}")

    # Просмотр данных
    st.header("3. Текущие траты")
    if not df.empty:
        st.dataframe(df)
        
        # Удаление трат
        st.subheader("Управление данными")
        selected_indices = st.multiselect(
            "Выберите траты для удаления",
            df["Описание трат"] + " (" + df["Сумма чека"].astype(str) + " руб)",
            key="expenses_to_delete"
        )
        
        if st.button("Удалить выбранные", key="delete_selected_btn"):
            if selected_indices:
                mask = ~(df["Описание трат"] + " (" + df["Сумма чека"].astype(str) + " руб)").isin(selected_indices)
                df = df[mask]
                try:
                    if sheet:
                        update_sheet(sheet, df)
                    st.success("Траты удалены!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка: {str(e)}")
            else:
                st.warning("Выберите траты для удаления")

    # Расчет долгов
    if not df.empty and st.session_state.people:
        st.header("4. Расчет долгов")
        
        total_spent = {p: 0 for p in st.session_state.people}
        total_share = {p: 0 for p in st.session_state.people}
        
        for _, row in df.iterrows():
            payer = row['Кто платил']
            total_spent[payer] += row['Сумма чека']
            
            participants = [p for p in st.session_state.people if row[p] == 1]
            if participants:
                share = row['Сумма чека'] / len(participants)
                for p in participants:
                    total_share[p] += share
        
        # Вывод результатов
        total = sum(total_spent.values())
        st.subheader(f"Общая сумма расходов: {total:.2f} руб")
        
        st.subheader("Баланс участников:")
        balances = {p: total_spent[p] - total_share[p] for p in st.session_state.people}
        balances_df = pd.DataFrame({
            "Участник": balances.keys(),
            "Баланс": [round(b, 2) for b in balances.values()]
        })
        st.dataframe(balances_df)
        
        # Расчет переводов
        st.subheader("Рекомендуемые переводы:")
        debtors = {p: -b for p, b in balances.items() if b < 0}
        creditors = {p: b for p, b in balances.items() if b > 0}
        
        transactions = []
        for creditor, amount in creditors.items():
            remaining = amount
            for debtor in debtors:
                if remaining <= 0:
                    break
                if debtors[debtor] > 0:
                    transfer = min(remaining, debtors[debtor])
                    if transfer > 1:
                        transactions.append({
                            "От": debtor,
                            "Кому": creditor,
                            "Сумма": round(transfer, 2)
                        })
                        remaining -= transfer
                        debtors[debtor] -= transfer
        
        if transactions:
            st.dataframe(pd.DataFrame(transactions))
        else:
            st.success("Все сбалансировано!")

if __name__ == "__main__":
    calculate_debts()
