import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import hashlib

# ============================================================================
# CONFIGURATION
# ============================================================================
ALL_MEMBERS = ["Youssef", "Essam", "Gharib", "Ayman"]
CURRENCY = "EGP"

# ============================================================================
# GOOGLE SHEETS CONNECTION
# ============================================================================
@st.cache_resource
def connect_to_sheet():
    """Connect to Google Sheets."""
    try:
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        client = gspread.authorize(credentials)
        sheet_id = st.secrets["sheets"]["id"]
        sheet = client.open_by_key(sheet_id)
        return sheet
    except Exception as e:
        st.error(f"❌ Error connecting to Google Sheets: {e}")
        return None

def read_users(sheet):
    """Read users and passwords from Users sheet."""
    try:
        worksheet = sheet.worksheet("Users")
        data = worksheet.get_all_records()
        return {user['Username']: user['Password'] for user in data}
    except Exception as e:
        st.error(f"Error reading users: {e}")
        return {}
        
def read_projects(sheet):
    try:
        worksheet = sheet.worksheet("Projects")
        data = worksheet.get_all_records()
        return data
    except:
        return []

def read_expenses(sheet):
    try:
        worksheet = sheet.worksheet("Expenses")
        data = worksheet.get_all_records()
        return data
    except:
        return []

def read_reimbursements(sheet):
    try:
        worksheet = sheet.worksheet("Reimbursements")
        data = worksheet.get_all_records()
        return data
    except:
        return []

def read_profit_splits(sheet):
    try:
        worksheet = sheet.worksheet("ProfitSplits")
        data = worksheet.get_all_records()
        return data
    except:
        return []

def add_expense(sheet, date, project, paid_by, description, amount, notes):
    try:
        worksheet = sheet.worksheet("Expenses")
        worksheet.append_row([date, project, paid_by, description, float(amount), notes])
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

def add_reimbursement(sheet, date, project, from_person, to_person, amount, notes):
    try:
        worksheet = sheet.worksheet("Reimbursements")
        worksheet.append_row([date, project, from_person, to_person, float(amount), notes])
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

def add_profit_split(sheet, project, member, percentage, notes):
    try:
        worksheet = sheet.worksheet("ProfitSplits")
        worksheet.append_row([project, member, float(percentage), notes])
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def get_user_projects(projects, username):
    """Get projects that the user is part of."""
    user_projects = []
    for project in projects:
        team_str = project.get("Team Members", "")
        team_members = [m.strip() for m in team_str.split(",")]
        if username in team_members:
            user_projects.append(project["Project Name"])
    return user_projects

def calculate_project_finances(project_name, expenses, reimbursements, profit_splits, project_budget, team_members):
    """Calculate financial breakdown for a project."""
    project_expenses = [e for e in expenses if e.get("Project") == project_name]
    project_reimbursements = [r for r in reimbursements if r.get("Project") == project_name]
    project_splits = [s for s in profit_splits if s.get("Project") == project_name]
    
    total_expenses = sum(float(e.get("Amount", 0)) for e in project_expenses)
    total_reimbursed = sum(float(r.get("Amount", 0)) for r in project_reimbursements)
    profit = project_budget - total_expenses
    
    member_data = {}
    
    # Initialize ALL team members from the project first
    for member in team_members:
        member_data[member] = {"expenses_paid": 0, "reimbursed": 0, "profit_share": 0, "profit_percentage": 0}
    
    for expense in project_expenses:
        paid_by = expense.get("Paid By")
        amount = float(expense.get("Amount", 0))
        if paid_by in member_data:
            member_data[paid_by]["expenses_paid"] += amount
    
    for reimb in project_reimbursements:
        to_person = reimb.get("To")
        amount = float(reimb.get("Amount", 0))
        if to_person in member_data:
            member_data[to_person]["reimbursed"] += amount
    
    for split in project_splits:
        member = split.get("Member")
        percentage = float(split.get("Percentage", 0))
        profit_amount = (percentage / 100) * profit
        if member in member_data:
            member_data[member]["profit_share"] = profit_amount
            member_data[member]["profit_percentage"] = percentage
    
    for member in member_data:
        expenses_paid = member_data[member]["expenses_paid"]
        reimbursed = member_data[member]["reimbursed"]
        profit_share = member_data[member]["profit_share"]
        member_data[member]["balance"] = profit_share + (expenses_paid - reimbursed)
    
    return {
        "total_expenses": total_expenses,
        "total_reimbursed": total_reimbursed,
        "profit": profit,
        "member_data": member_data
    }

# ============================================================================
# CUSTOM CSS
# ============================================================================
def apply_custom_css():
    st.markdown("""
    <style>
        .stApp { background-color: #f5f7fa; }
        .main-header {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            padding: 2rem;
            border-radius: 15px;
            color: white;
            text-align: center;
            margin-bottom: 2rem;
        }
        .balance-positive { color: #28a745; font-weight: bold; }
        .balance-negative { color: #dc3545; font-weight: bold; }
        .balance-zero { color: #6c757d; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# ============================================================================
# MAIN APP
# ============================================================================
def main():
    st.set_page_config(
        page_title="Project Expense Tracker",
        page_icon="💼",
        layout="wide"
    )
    
    apply_custom_css()
    
    st.markdown("""
    <div class="main-header">
        <h1>💼 Freelance Team Project Tracker</h1>
        <p>Manage expenses, reimbursements, and profit sharing</p>
    </div>
    """, unsafe_allow_html=True)
    
    if "logged_in_user" not in st.session_state:
        st.session_state.logged_in_user = None
    
    if not st.session_state.logged_in_user:
        sheet = connect_to_sheet()
        if not sheet:
            st.error("❌ Cannot connect to Google Sheets")
            return
        
        users = read_users(sheet)
        
        st.subheader("🔐 Login")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            selected_user = st.selectbox("Select your name:", [""] + ALL_MEMBERS)
            password_input = st.text_input("Password:", type="password")
            
            if st.button("Login", type="primary"):
                if not selected_user:
                    st.error("Please select your name")
                elif not password_input:
                    st.error("Please enter password")
                elif selected_user not in users:
                    st.error("User not found")
                elif password_input != users[selected_user]:
                    st.error("❌ Incorrect password")
                else:
                    st.session_state.logged_in_user = selected_user
                    st.rerun()
        return
    
    username = st.session_state.logged_in_user
    
    with st.sidebar:
        st.success(f"✅ Logged in as: **{username}**")
        if st.button("🚪 Logout"):
            st.session_state.logged_in_user = None
            st.rerun()
        st.markdown("---")
    
    sheet = connect_to_sheet()
    if not sheet:
        st.error("❌ Cannot connect to Google Sheets")
        return
    
    projects = read_projects(sheet)
    expenses = read_expenses(sheet)
    reimbursements = read_reimbursements(sheet)
    profit_splits = read_profit_splits(sheet)
    
    user_projects = get_user_projects(projects, username)
    
    if not user_projects:
        st.warning(f"⚠️ You are not assigned to any projects yet.")
        return
    
    selected_project_name = st.selectbox("📁 Select Project:", user_projects)
    
    selected_project = next((p for p in projects if p["Project Name"] == selected_project_name), None)
    if not selected_project:
        st.error("Project not found")
        return
    
    project_budget = float(selected_project.get("Budget", 0))
    project_status = selected_project.get("Status", "Active")
    team_members_str = selected_project.get("Team Members", "")
    team_members = [m.strip() for m in team_members_str.split(",")]
    
    finances = calculate_project_finances(
        selected_project_name, 
        expenses, 
        reimbursements, 
        profit_splits,
        project_budget,
        team_members
    )
    
    # Filter project transactions
    project_expenses = [e for e in expenses if e.get("Project") == selected_project_name]
    project_reimbursements = [r for r in reimbursements if r.get("Project") == selected_project_name]
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard", 
        "💰 Add Expense", 
        "💸 Money Flow",
        "📈 Set Profit Split",
        "📋 Transaction History"
    ])
    
    with tab1:
        st.subheader(f"📁 {selected_project_name}")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Budget", f"{project_budget:,.2f} {CURRENCY}")
        with col2:
            st.metric("Total Expenses", f"{finances['total_expenses']:,.2f} {CURRENCY}")
        with col3:
            st.metric("Profit", f"{finances['profit']:,.2f} {CURRENCY}")
        with col4:
            st.metric("Status", project_status)
        
        st.markdown("---")
        st.subheader("👥 Team Financial Breakdown")
        
        if finances['member_data']:
            for member in team_members:
                if member in finances['member_data']:
                    data = finances['member_data'][member]
                    
                    with st.expander(f"👤 {member}", expanded=(member == username)):
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Expenses Paid", f"{data['expenses_paid']:,.2f} {CURRENCY}")
                        with col2:
                            st.metric("Money Received", f"{data['reimbursed']:,.2f} {CURRENCY}")
                        with col3:
                            st.metric("Profit Share", f"{data['profit_share']:,.2f} {CURRENCY}")
                            st.caption(f"{data['profit_percentage']:.1f}%")
                        with col4:
                            balance = data['balance']
                            if balance > 0.01:
                                st.markdown(f"**Final Balance:**")
                                st.markdown(f'<p class="balance-positive">+{balance:,.2f} {CURRENCY}</p>', unsafe_allow_html=True)
                                st.caption("To Receive")
                            elif balance < -0.01:
                                st.markdown(f"**Final Balance:**")
                                st.markdown(f'<p class="balance-negative">{balance:,.2f} {CURRENCY}</p>', unsafe_allow_html=True)
                                st.caption("Holding Project Money")
                            else:
                                st.markdown(f"**Final Balance:**")
                                st.markdown(f'<p class="balance-zero">0.00 {CURRENCY}</p>', unsafe_allow_html=True)
                                st.caption("Settled")
        else:
            st.info("No financial data yet for this project")
    
    with tab2:
        st.subheader("💰 Add Project Expense")
        
        with st.form("expense_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                expense_date = st.date_input("Date", datetime.now())
                expense_paid_by = st.selectbox("Paid By", team_members)
                expense_amount = st.number_input(f"Amount ({CURRENCY})", min_value=0.0, step=0.01)
            
            with col2:
                expense_description = st.text_input("Description", placeholder="e.g., Components, Materials")
                expense_notes = st.text_area("Notes (optional)")
            
            submit = st.form_submit_button("💾 Add Expense")
            
            if submit:
                if not expense_description:
                    st.error("Please enter a description")
                elif expense_amount <= 0:
                    st.error("Amount must be positive")
                else:
                    date_str = expense_date.strftime("%Y-%m-%d")
                    if add_expense(sheet, date_str, selected_project_name, expense_paid_by,
                                   expense_description, expense_amount, expense_notes):
                        st.success(f"✅ Expense added! {expense_paid_by} paid {expense_amount:,.2f} {CURRENCY}")
                        st.balloons()
                        st.rerun()
    
    with tab3:
        st.subheader("💸 Track Money Flow")
        st.info("💡 Record client payments OR money transfers between team members")
        
        with st.form("reimbursement_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                reimb_date = st.date_input("Date", datetime.now())
                reimb_from = st.selectbox("From (Source)", ["Client"] + team_members)
                reimb_to = st.selectbox("To (Recipient)", team_members)
            
            with col2:
                reimb_amount = st.number_input(f"Amount ({CURRENCY})", min_value=0.0, step=0.01)
                reimb_notes = st.text_area("Notes (optional)", placeholder="e.g., Client installment, Payback for materials")
            
            submit = st.form_submit_button("💾 Record Payment")
            
            if submit:
                if reimb_from == reimb_to:
                    st.error("Source and recipient must be different")
                elif reimb_amount <= 0:
                    st.error("Amount must be positive")
                else:
                    date_str = reimb_date.strftime("%Y-%m-%d")
                    if add_reimbursement(sheet, date_str, selected_project_name, reimb_from,
                                        reimb_to, reimb_amount, reimb_notes):
                        if reimb_from == "Client":
                            st.success(f"✅ Client payment recorded! {reimb_to} received {reimb_amount:,.2f} {CURRENCY}")
                        else:
                            st.success(f"✅ Payment recorded! {reimb_from} → {reimb_to}: {reimb_amount:,.2f} {CURRENCY}")
                        st.rerun()
    
    with tab4:
        st.subheader("📈 Set Profit Split Percentages")
        
        st.info(f"💡 Current profit to split: **{finances['profit']:,.2f} {CURRENCY}**")
        
        current_splits = [s for s in profit_splits if s.get("Project") == selected_project_name]
        if current_splits:
            st.markdown("**Current Splits:**")
            total_pct = 0
            for split in current_splits:
                pct = float(split.get('Percentage', 0))
                total_pct += pct
                st.write(f"- {split['Member']}: {pct}%")
            if abs(total_pct - 100) > 0.1:
                st.warning(f"⚠️ Total: {total_pct}% (should equal 100%)")
            else:
                st.success(f"✅ Total: {total_pct}%")
        
        st.markdown("---")
        
        with st.form("profit_split_form"):
            split_member = st.selectbox("Team Member", team_members)
            split_percentage = st.number_input("Percentage (%)", min_value=0.0, max_value=100.0, step=0.1)
            split_notes = st.text_input("Notes (optional)", placeholder="e.g., Lead developer")
            
            submit = st.form_submit_button("💾 Add/Update Split")
            
            if submit:
                if split_percentage <= 0:
                    st.error("Percentage must be positive")
                else:
                    if add_profit_split(sheet, selected_project_name, split_member, split_percentage, split_notes):
                        st.success(f"✅ Profit split updated: {split_member} = {split_percentage}%")
                        st.rerun()
    
    with tab5:
        st.subheader("📋 Transaction History")
        
        # Create expenses dataframe
        if project_expenses:
            expenses_df = pd.DataFrame(project_expenses)
            expenses_df['Type'] = '💰 Expense'
            expenses_df = expenses_df.rename(columns={
                'Date': 'Date',
                'Paid By': 'Person',
                'Description': 'Description',
                'Amount': 'Amount',
                'Notes': 'Notes'
            })
            expenses_df = expenses_df[['Date', 'Type', 'Person', 'Description', 'Amount', 'Notes']]
        else:
            expenses_df = pd.DataFrame(columns=['Date', 'Type', 'Person', 'Description', 'Amount', 'Notes'])
        
        # Create reimbursements dataframe
        if project_reimbursements:
            reimb_df = pd.DataFrame(project_reimbursements)
            reimb_df['Type'] = '💸 Payment'
            reimb_df['Description'] = reimb_df['From'] + ' → ' + reimb_df['To']
            reimb_df['Person'] = reimb_df['To']
            reimb_df = reimb_df.rename(columns={
                'Date': 'Date',
                'Amount': 'Amount',
                'Notes': 'Notes'
            })
            reimb_df = reimb_df[['Date', 'Type', 'Person', 'Description', 'Amount', 'Notes']]
        else:
            reimb_df = pd.DataFrame(columns=['Date',            reimb_df = pd.DataFrame(columns=['Date', 'Type', 'Person', 'Description', 'Amount', 'Notes'])
        
        # Combine all transactions
        if not expenses_df.empty or not reimb_df.empty:
            all_transactions = pd.concat([expenses_df, reimb_df], ignore_index=True)
            all_transactions = all_transactions.sort_values('Date', ascending=False)
            
            # Display filters
            col1, col2 = st.columns(2)
            with col1:
                filter_type = st.multiselect("Filter by Type:", ['💰 Expense', '💸 Payment'], default=['💰 Expense', '💸 Payment'])
            with col2:
                filter_person = st.multiselect("Filter by Person:", team_members, default=team_members)
            
            # Apply filters
            filtered_df = all_transactions[
                (all_transactions['Type'].isin(filter_type)) &
                (all_transactions['Person'].isin(filter_person))
            ]
            
            if not filtered_df.empty:
                st.dataframe(
                    filtered_df,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Summary stats
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                with col1:
                    total_expense_transactions = len(filtered_df[filtered_df['Type'] == '💰 Expense'])
                    st.metric("Total Expenses", total_expense_transactions)
                with col2:
                    total_payment_transactions = len(filtered_df[filtered_df['Type'] == '💸 Payment'])
                    st.metric("Total Payments", total_payment_transactions)
                with col3:
                    total_amount = filtered_df['Amount'].sum()
                    st.metric("Total Amount", f"{total_amount:,.2f} {CURRENCY}")
            else:
                st.info("No transactions match the selected filters")
        else:
            st.info("📭 No transactions recorded yet for this project")

if __name__ == "__main__":
    main()
