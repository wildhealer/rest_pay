import streamlit as st
import pandas as pd
import json
from io import BytesIO

def save_data_to_json():
    """Сохраняет данные в JSON формате"""
    data = {
        'people': st.session_state.people,
        'bills': st.session_state.bills.to_dict('records')
    }
    return json.dumps(data)

def load_data_from_json(uploaded_file):
    """Загружает данные из JSON файла"""
    data = json.load(uploaded_file)
    st.session_state.people = data['people']
    st.session_state.bills = pd.DataFrame(data['bills'])

def calculate_debts():
    st.title("🍽️ Калькулятор долгов в ресторане")
    st.write("Рассчитаем, кто сколько должен после вечера в ресторане")

    # Инициализация данных в session state
    if 'people' not in st.session_state:
        st.session_state.people = ["Иха", "Локи", "Влад"]
    if 'bills' not in st.session_state:
        st.session_state.bills = pd.DataFrame(columns=["Заведение", "Сумма", "Оплативший", "Участники"])

    # Управление участниками
    st.header("1. Участники")
    
    col1, col2 = st.columns(2)
    with col1:
        new_person = st.text_input("Добавить нового участника")
        if st.button("Добавить участника") and new_person:
            st.session_state.people.append(new_person)
            st.rerun()
    
    with col2:
        if st.session_state.people:
            to_remove = st.selectbox("Удалить участника", st.session_state.people)
            if st.button("Удалить участника"):
                st.session_state.people.remove(to_remove)
                st.rerun()

    st.write("Текущие участники:", ", ".join(st.session_state.people))

    # Добавление счетов
    st.header("2. Добавление счетов")
    
    with st.form("bill_form"):
        place = st.text_input("Заведение (название ресторана/бара)")
        amount = st.number_input("Сумма счёта (руб)", min_value=1, value=1000)
        payer = st.selectbox("Кто оплатил", st.session_state.people)
        
        # Выбор участников для этого счета
        default_consumers = st.session_state.people
        consumers = st.multiselect(
            "Кто участвовал (по умолчанию все)", 
            st.session_state.people, 
            default=default_consumers
        )
        
        submitted = st.form_submit_button("Добавить счёт")
        if submitted and place and amount and payer and consumers:
            new_bill = {
                "Заведение": place,
                "Сумма": amount,
                "Оплативший": payer,
                "Участники": ", ".join(consumers),
                "Доля на человека": amount / len(consumers) if consumers else 0
            }
            st.session_state.bills = pd.concat([
                st.session_state.bills, 
                pd.DataFrame([new_bill])
            ], ignore_index=True)
            st.rerun()

    # Управление счетами
    if not st.session_state.bills.empty:
        st.subheader("Управление счетами")
        
        # Экспорт данных
        st.download_button(
            label="Сохранить данные",
            data=save_data_to_json(),
            file_name="restaurant_bills.json",
            mime="application/json"
        )
        
        # Импорт данных
        uploaded_file = st.file_uploader("Загрузить сохранённые данные", type="json")
        if uploaded_file is not None:
            load_data_from_json(uploaded_file)
            st.rerun()
        
        # Удаление счетов
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Очистить все счета"):
                st.session_state.bills = pd.DataFrame(columns=["Заведение", "Сумма", "Оплативший", "Участники"])
                st.rerun()
        
        with col2:
            if not st.session_state.bills.empty:
                bill_to_remove = st.selectbox(
                    "Выберите счёт для удаления",
                    st.session_state.bills["Заведение"] + " (" + st.session_state.bills["Сумма"].astype(str) + " руб)"
                )
                if st.button("Удалить выбранный счёт"):
                    index_to_remove = st.session_state.bills.index[
                        (st.session_state.bills["Заведение"] + " (" + st.session_state.bills["Сумма"].astype(str) + " руб)") == bill_to_remove
                    ].tolist()[0]
                    st.session_state.bills = st.session_state.bills.drop(index_to_remove).reset_index(drop=True)
                    st.rerun()

        st.subheader("Добавленные счета")
        st.dataframe(st.session_state.bills)

    # Расчет долгов
    if not st.session_state.bills.empty and st.session_state.people:
        st.header("3. Итоговые расчеты")
        
        # Рассчет: сколько каждый должен в идеале
        total_spent = {person: 0 for person in st.session_state.people}
        total_share = {person: 0 for person in st.session_state.people}
        
        for _, bill in st.session_state.bills.iterrows():
            # Кто оплатил
            payer = bill['Оплативший']
            total_spent[payer] += bill['Сумма']
            
            # Доли участников
            participants = bill['Участники'].split(', ')
            share = bill['Сумма'] / len(participants)
            for person in participants:
                total_share[person.strip()] += share
        
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
    calculate_debts()
