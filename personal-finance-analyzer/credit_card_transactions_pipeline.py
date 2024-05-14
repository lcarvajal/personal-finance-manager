'''
This program takes temporary credit card transaction data, cleans it up, and adds it to a CSV file containing a history of all credit card transactions.
'''

from datetime import datetime
from dotenv import load_dotenv
import os
from openai import OpenAI
import pandas as pd
import send2trash
from transaction_category import categorize_transactions, check_for_approved_categories, get_category_from_api
import constant as c

load_dotenv()
OPENAI_API_KEY = os.getenv(c.OPEN_AI_KEY)

TEMP_FILES = [f for f in os.listdir(c.TEMP_DIRECTORY_PATH) if os.path.isfile(os.path.join(c.TEMP_DIRECTORY_PATH, f))]
CSV_FILES = [s for s in TEMP_FILES if s.lower().endswith('csv')] 

# Extract

def extract_capital_one_transactions(csv):
    """Reads a Capital One CSV file and preprocesses it."""
    df = pd.read_csv(csv, encoding='latin-1')
    
    df = df.rename(columns={
        'Transaction Date': c.DATE, 
        'Card No.': c.CARD_NUMBER, 
        'Description': c.BUSINESS_OR_PERSON_ORIGINAL, 
        'Category': c.CATEGORY, 
        'Debit': c.DEBIT, 
        'Credit': c.CREDIT })
    
    # Check dataframe is in expected format.
    expected_columns = [c.DATE, c.CARD_NUMBER, c.BUSINESS_OR_PERSON_ORIGINAL, c.CATEGORY, c.DEBIT, c.CREDIT]
    if not all(col in df.columns for col in expected_columns):
        raise ValueError("DataFrame is missing one or more expected columns.")

    return df

def extract_transaction_history():
    # Add rows from transaction history to current transactions data frame.
    if os.path.exists(c.TRANSACTIONS_HISTORY_FILE_PATH):
        return pd.read_csv(c.TRANSACTIONS_HISTORY_FILE_PATH)
    else:
        raise FileExistsError("Transaction history file missing.")

# Transform

def clean_capital_one_transactions(df):
    df[c.BUSINESS_OR_PERSON_ORIGINAL] = df[c.BUSINESS_OR_PERSON_ORIGINAL].str.lower()
    df[c.BUSINESS_OR_PERSON] = df[c.BUSINESS_OR_PERSON_ORIGINAL].str.replace('[\d#]+', '', regex=True)
    df = df.dropna(subset=[c.DEBIT])
    df.drop('Posted Date', axis=1, inplace=True)
    return df

def clean_transaction_history(df):
    # Remove transactions that have already been added.
    df = df.drop_duplicates(subset=[c.DATE, c.BUSINESS_OR_PERSON_ORIGINAL, c.DEBIT, c.SEQUENCE])
    # Sort by date.
    df = df.sort_values(by=[c.DATE, c.CATEGORY, c.BUSINESS_OR_PERSON], ascending=[False, True, True])
    return df

def set_unique_identifiers(df):
    # Create a unique identifier for each transaction.
    df[c.SEQUENCE] = df.groupby([c.DATE, c.CARD_NUMBER, c.BUSINESS_OR_PERSON_ORIGINAL, c.DEBIT]).cumcount() + 1
    return df

# Load

def load_transactions(df):
    # Get today's date
    today_date = datetime.today().strftime('%Y-%m-%d')

    # Create filename with today's date
    filename = f"transactions_{today_date}.csv"
    df.to_csv(c.IMPORTED_TRANSACTIONS_DIRECTORY_PATH + filename, index=False)

def send_csv_files_to_trash():
    """Moves CSV files in temp directory to trash."""
    for file in CSV_FILES:
        file_path = c.TEMP_DIRECTORY_PATH + file

        # Check if the file exists before attempting to delete
        if os.path.exists(file_path):
            # Move the file to the trash
            send2trash.send2trash(file_path)
            print(f"File '{file_path}' moved to trash successfully.")
        else:
            print(f"File '{file_path}' does not exist.")

# Main

def main():
    # Extract data by looping through CSVs in temp and add them all to one dataframe
    transactions_df = pd.DataFrame()

    for file in CSV_FILES:
        df = extract_capital_one_transactions(c.TEMP_DIRECTORY_PATH + file)
        df = clean_capital_one_transactions(df)
        df = categorize_transactions(df)
        df = set_unique_identifiers(df)
        df['category'] = df.apply(get_category_from_api, axis=1)
        transactions_df = pd.concat([transactions_df, df])

    if transactions_df.empty:
        return
    else:
        load_transactions(transactions_df)

        transaction_history_df = extract_transaction_history()
        transaction_history_df = pd.concat([transactions_df, transaction_history_df], ignore_index=True)
        transaction_history_df = clean_transaction_history(transaction_history_df)
        # Save for long-term storage.
        transactions_df.to_csv(c.TRANSACTIONS_HISTORY_FILE_PATH, index=False)

        check_for_approved_categories(transactions_df)
        send_csv_files_to_trash()

if __name__ == "__main__":
    main()