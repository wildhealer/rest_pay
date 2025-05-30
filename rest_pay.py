import streamlit as st
import pandas as pd

def calculate_debts():
    st.title("🍽️ Калькулятор долгов в ресторане")
    st.write("Рассчитаем, кто сколько должен после вечера в ресторане")

    # Ввод участников
    st.header("1. Участники")
    num_people = st.number_input("Количество человек", min_value=2, max_value=20, value=4)
    
    people = []
    for i in range(num_people):
        name = st.text_input(f"Имя участника {i+1}", value=f"Участник {i+1}")
        people.append(name)

    # Ввод заказов
    st.header("2. Заказы и расходы")
    st.write("Укажите, кто что заказывал и сколько это стоило")

    orders = []
    if 'orders_df' not in st.session_state:
        st.session_state.orders_df = pd.DataFrame(columns=["Позиция", "Стоимость", "Кто ел"])

    with st.form("order_form"):
        item = st.text_input("Позиция в меню (например, 'Пицца Маргарита')")
        cost = st.number_input("Стоимость (руб)", min_value=0, value=500)
        consumers = st.multiselect("Кто ел эту позицию", people)
        
        submitted = st.form_submit_button("Добавить заказ")
        if submitted and item and cost > 0 and consumers:
            new_order = {
                "Позиция": item,
                "Стоимость": cost,
                "Кто ел": ", ".join(consumers),
                "На человека": cost / len(consumers) if len(consumers) > 0 else 0
            }
            st.session_state.orders_df = pd.concat([
                st.session_state.orders_df, 
                pd.DataFrame([new_order])
            ], ignore_index=True)

    # Показать добавленные заказы
    if not st.session_state.orders_df.empty:
        st.subheader("Добавленные заказы")
        st.dataframe(st.session_state.orders_df)
        
        if st.button("Очистить все заказы"):
            st.session_state.orders_df = pd.DataFrame(columns=["Позиция", "Стоимость", "Кто ел"])
            st.rerun()

    # Расчет долгов
    if not st.session_state.orders_df.empty:
        st.header("3. Итоговые расчеты")
        
        # Рассчет долгов
        debts = {person: 0 for person in people}
        for _, row in st.session_state.orders_df.iterrows():
            cost_per_person = row['Стоимость'] / len(row['Кто ел'].split(', '))
            for person in row['Кто ел'].split(', '):
                debts[person.strip()] += cost_per_person
        
        # Рассчет общего счета
        total = sum(debts.values())
        st.subheader(f"Общий счет: {total:.2f} руб")
        
        # Показать долги каждого
        st.subheader("Долги каждого участника:")
        debts_df = pd.DataFrame.from_dict(debts, orient='index', columns=['Долг'])
        debts_df["Долг"] = debts_df["Долг"].round(2)
        st.dataframe(debts_df)
        
        # Рассчет переводов
        st.subheader("Кому сколько перевести:")
        avg = total / len(people)
        payers = {p: d - avg for p, d in debts.items()}
        
        transactions = []
        debtors = {p: a for p, a in payers.items() if a < 0}
        creditors = {p: a for p, a in payers.items() if a > 0}
        
        for creditor, amount in creditors.items():
            remaining = amount
            for debtor, debt in debtors.items():
                if remaining <= 0:
                    break
                if debt < 0:
                    transfer = min(remaining, -debt)
                    transactions.append({
                        "От": debtor,
                        "Кому": creditor,
                        "Сумма": transfer
                    })
                    remaining -= transfer
                    debtors[debtor] += transfer
        
        transactions_df = pd.DataFrame(transactions)
        st.dataframe(transactions_df)

if __name__ == "__main__":
    calculate_debts()
