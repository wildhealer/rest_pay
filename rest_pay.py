import streamlit as st
import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials



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

'''
def get_sheet_data():
    client = connect_to_gsheet()
    sheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)
    data = sheet.get_all_records()
    return pd.DataFrame(data), sheet
'''
def get_sheet_data():
    client = connect_to_gsheet()
    sheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)
    
    # Вариант 1: с явным указанием заголовков
    expected_headers = ["Кто платил", "Описание трат", "Сумма чека", "Иха", "Влад", "Локи"]
    data = sheet.get_all_records(expected_headers=expected_headers)
    
    # Вариант 2: ручная обработка (надежнее)
    raw_data = sheet.get_all_values()
    if not raw_data:
        return pd.DataFrame(columns=expected_headers), sheet
        
    headers = raw_data[0]
    records = raw_data[1:]
    df = pd.DataFrame(records, columns=headers)
    
    return df, sheet

def update_sheet(sheet, df):
    # Очищаем лист, кроме заголовков
    sheet.clear()
    # Записываем данные с заголовками
    set_with_dataframe(sheet, df)

def calculate_debts():
    st.title("🍽️ Калькулятор долгов с синхронизацией Google Sheets")
    
    # Загружаем данные из Google Sheets
    try:
        df, sheet = get_sheet_data()
        st.session_state.people = [col for col in df.columns if col not in ["Кто платил", "Описание трат", "Сумма чека"]]
    except Exception as e:
        st.error(f"Ошибка загрузки данных: {e}")
        df = pd.DataFrame(columns=["Кто платил", "Описание трат", "Сумма чека"] + ["Иха", "Влад", "Локи"])
        st.session_state.people = ["Иха", "Влад", "Локи"]
    
    # Основной интерфейс
    st.header("1. Добавление новых трат")
    
    with st.form("expense_form"):
        payer = st.selectbox("Кто платил", st.session_state.people)
        description = st.text_input("Описание трат (место/ресторан)")
        amount = st.number_input("Сумма чека", min_value=1, value=1000)
        
        st.write("Кто участвовал в этой трате:")
        participants = {}
        cols = st.columns(3)
        for i, person in enumerate(st.session_state.people):
            with cols[i % 3]:
                participants[person] = st.checkbox(person, value=True, key=f"part_{person}")
        
        submitted = st.form_submit_button("Добавить трату")
        
        if submitted:
            new_row = {
                "Кто платил": payer,
                "Описание трат": description,
                "Сумма чека": amount
            }
            for person in st.session_state.people:
                new_row[person] = 1 if participants[person] else 0
            
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            try:
                update_sheet(sheet, df)
                st.success("Трата успешно добавлена в Google Sheets!")
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка сохранения: {e}")

    # Просмотр и редактирование данных
    st.header("2. Текущие траты")
    st.dataframe(df)
    
    # Удаление трат
    st.header("3. Управление данными")
    
    if not df.empty:
        with st.expander("Удалить траты"):
            selected_indices = st.multiselect(
                "Выберите траты для удаления (по описанию)",
                df["Описание трат"] + " (" + df["Сумма чека"].astype(str) + " руб)"
            )
            
            if st.button("Удалить выбранные"):
                mask = ~(df["Описание трат"] + " (" + df["Сумма чека"].astype(str) + " руб)").isin(selected_indices)
                df = df[mask]
                try:
                    update_sheet(sheet, df)
                    st.success("Траты удалены!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка сохранения: {e}")
    
    # Расчет долгов
    st.header("4. Расчет долгов")
    
    if not df.empty:
        # Рассчет: сколько каждый должен в идеале
        total_spent = {person: 0 for person in st.session_state.people}
        total_share = {person: 0 for person in st.session_state.people}
        
        for _, row in df.iterrows():
            # Кто оплатил
            payer = row['Кто платил']
            total_spent[payer] += row['Сумма чека']
            
            # Доли участников
            participants = [p for p in st.session_state.people if row[p] == 1]
            if participants:
                share = row['Сумма чека'] / len(participants)
                for person in participants:
                    total_share[person] += share
        
        # Общая сумма
        total = sum(total_spent.values())
        st.subheader(f"Общая сумма расходов: {total:.2f} руб")
        
        # Показать сколько каждый оплатил и его долю
        st.subheader("Статистика по участникам:")
        stats_df = pd.DataFrame({
            "Участник": st.session_state.people,
            "Оплатил": [total_spent[p] for p in st.session_state.people],
            "Доля": [total_share[p] for p in st.session_state.people],
            "Баланс": [round(total_spent[p] - total_share[p], 2) for p in st.session_state.people]
        })
        st.dataframe(stats_df)
        
        # Рассчет переводов
        st.subheader("Кому сколько перевести:")
        
        balances = {p: total_spent[p] - total_share[p] for p in st.session_state.people}
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
                    if transfer > 1:  # Не показывать переводы меньше 1 рубля
                        transactions.append({
                            "От": debtor,
                            "Кому": creditor,
                            "Сумма": round(transfer, 2)
                        })
                        remaining -= transfer
                        debtors[debtor] -= transfer
        
        if transactions:
            transactions_df = pd.DataFrame(transactions)
            st.dataframe(transactions_df)
        else:
            st.success("Все сбалансировано, переводы не требуются!")

if __name__ == "__main__":
    # Необходимо добавить секреты в secrets.toml:
    # [gcp_service_account]
    # type = "service_account"
    # project_id = "..."
    # private_key_id = "..."
    # private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
    # client_email = "..."
    # client_id = "..."
    # auth_uri = "https://accounts.google.com/o/oauth2/auth"
    # token_uri = "https://oauth2.googleapis.com/token"
    # auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
    # client_x509_cert_url = "..."
    
    calculate_debts()
