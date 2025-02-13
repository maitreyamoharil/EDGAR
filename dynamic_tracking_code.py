'''
Dynamic tracking File
'''

from filing_processor import get_filing_list_from_dynamic_script
from filing_processor import send_multiple_docx_email
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import time
import os  # Add this line to import the os module
import smtplib
from queue import Queue
import threading
import schedule
from flask import Flask
from flask_mail import Mail, Message
import pytz
import requests
import psycopg2

# Database configuration
db_config = {
    "host": "localhost",
    "database": "edgar",
    "user": "postgres",
    "password": "password",
    "port": "5432"
}


app = Flask(__name__)
app.secret_key = "your_secret_key"  # Ensure you set a secret key for sessions

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "maitreyamoharil@gmail.com"  # Replace with your email
app.config["MAIL_PASSWORD"] = (
    "vacq nmbk htph bdyw"  # Use app password if 2FA is enabled
)
app.config["MAIL_DEFAULT_SENDER"] = "maitreyamoharil@gmail.com"

# arithwisesolutions@gmail.com
# maitreyamoharil@gmail.com
# vacq nmbk htph bdyw -> Maitreya's app password
# ukka ersj ixok zfbp -> Arithwise's app password

mail = Mail(app)

# Constants for Time Zones
UTC = pytz.UTC

def get_db_connection():
    """
    Creates and returns a connection to the PostgreSQL database using the configured credentials.

    Returns:
        psycopg2.connection: A connection object to the PostgreSQL database
    """
    conn = psycopg2.connect(
        host=db_config["host"],
        database=db_config["database"],
        user=db_config["user"],
        password=db_config["password"],
        port=db_config["port"],
    )
    return conn

def get_client_information():
    '''
    Get client information
    '''
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT client_id, client_email FROM client_information")
    client_id, client_email = cur.fetchone()
    cur.close()
    conn.close()
    return client_id, client_email

CLIENT_ID, CLIENT_EMAIL = get_client_information()


def dynamic_tracking():
    '''
    Dynamic tracking with queued processing for tickers
    '''
    # Create a queue for processing tickers
    ticker_queue = Queue()

    def process_ticker(ticker, target_date):
        '''
        Process a single ticker from the queue
        '''
        try:
            print(f"Processing ticker: {ticker}")
            cik = fetch_cik_by_ticker_inner(ticker)
            if not cik:
                print(f"CIK not found for ticker {ticker}")
                return

            filings = fetch_rss_feed(cik)
            filtered_filings = filter_filings_by_date_inner(filings, target_date)

            if filtered_filings:
                # Process filings sequentially
                check_todays_filings_and_notify(ticker, target_date, filtered_filings)
                update_tracking_table_and_notify(ticker, filtered_filings[:3])

            print(f"Completed processing ticker: {ticker}")

        except ValueError as e:
            print(f"Error processing ticker {ticker}: {e}")

    def worker():
        '''
        Worker function to process tickers from the queue
        '''
        while True:
            try:
                # Get ticker and target_date from queue
                ticker, target_date = ticker_queue.get()
                if ticker is None:  # Poison pill to stop worker
                    break

                process_ticker(ticker, target_date)

            except ValueError as e:
                print(f"Worker error: {e}")
            finally:
                ticker_queue.task_done()

    # Modify the main function to use the queue
    def main(date_str):
        '''
        Main function with queued processing
        '''
        try:
            conn = get_db_connection()
            if not conn:
                return

            cur = conn.cursor()
            cur.execute("SELECT ticker FROM tracking")
            tickers = [row[0] for row in cur.fetchall()]

            target_date = datetime.strptime(date_str, '%d-%m-%Y').date()

            # Create and start worker thread
            worker_thread = threading.Thread(target=worker)
            worker_thread.start()

            # Add all tickers to the queue
            for ticker in tickers:
                ticker_queue.put((ticker, target_date))

            # Add poison pill to stop worker
            ticker_queue.put((None, None))

            # Wait for all tasks to complete
            ticker_queue.join()
            worker_thread.join()

            print("All tickers processed successfully")

        except ValueError as e:
            print(f"Error in main function: {e}")
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()

    # Scheduling function
    def job():
        '''
        Scheduling function
        '''

        # Subtract one day from the current date
        yesterday = east_now - timedelta(days=1)

        # Only print in the main process
        if not os.environ.get('WERKZEUG_RUN_MAIN'):
            print(f"Current time (India): {india_now}")
            print(f"Current time (EST): {east_now.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Job running at (EST): {yesterday.strftime('%Y-%m-%d %H:%M:%S')}")

        date_str = yesterday.strftime('%d-%m-%Y')

        main(date_str)

    def update_watchlist_filings(ticker, filings):
        """
        Updates watchlist table with new filing information for a given ticker.
        
        Args:
            ticker (str): Stock ticker symbol
            filings (list): List of filing dictionaries containing updated filing information
            
        Returns:
            dict: Response indicating success/failure and message
        """
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # Prepare the filing data (take first 3 filings)
            filing_data = {
                'filing1_title': filings[0]['title'] if len(filings) > 0 else None,
                'filing1_link': filings[0]['link'] if len(filings) > 0 else None,
                'filing1_date': filings[0]['updated'] if len(filings) > 0 else None,
                'filing1_type': filings[0]['filing_type'] if len(filings) > 0 else None,
                'filing2_title': filings[1]['title'] if len(filings) > 1 else None,
                'filing2_link': filings[1]['link'] if len(filings) > 1 else None,
                'filing2_date': filings[1]['updated'] if len(filings) > 1 else None,
                'filing2_type': filings[1]['filing_type'] if len(filings) > 1 else None,
                'filing3_title': filings[2]['title'] if len(filings) > 2 else None,
                'filing3_link': filings[2]['link'] if len(filings) > 2 else None,
                'filing3_date': filings[2]['updated'] if len(filings) > 2 else None,
                'filing3_type': filings[2]['filing_type'] if len(filings) > 2 else None,
            }

            # Update the watchlist table
            update_query = """
            UPDATE watchlist 
            SET 
                filing_title_1 = %s, filing_link_1 = %s, filing_date_1 = %s, filing_type_1 = %s,
                filing_title_2 = %s, filing_link_2 = %s, filing_date_2 = %s, filing_type_2 = %s,
                filing_title_3 = %s, filing_link_3 = %s, filing_date_3 = %s, filing_type_3 = %s
            WHERE ticker = %s
            """

            cur.execute(
                update_query,
                (
                    filing_data['filing1_title'], filing_data['filing1_link'],
                    filing_data['filing1_date'], filing_data['filing1_type'],
                    filing_data['filing2_title'], filing_data['filing2_link'],
                    filing_data['filing2_date'], filing_data['filing2_type'],
                    filing_data['filing3_title'], filing_data['filing3_link'],
                    filing_data['filing3_date'], filing_data['filing3_type'],
                    ticker
                )
            )

            conn.commit()

        except (psycopg2.Error, ValueError, KeyError) as e:
            print(f"Error updating watchlist: {e}")
            return {
                "success": False,
                "message": f"Error updating watchlist: {str(e)}"
            }
        finally:
            cur.close()
            conn.close()

    # Function to fetch CIK by ticker
    def fetch_cik_by_ticker_inner(ticker):
        '''
        Fetch CIK by ticker
        '''
        try:
            conn = get_db_connection()
            if not conn:
                return None
            cur = conn.cursor()
            cur.execute("SELECT cik FROM company_list WHERE ticker = %s", (ticker,))
            result = cur.fetchone()
            cur.close()
            conn.close()
            return result[0] if result else None
        except psycopg2.Error as db_err:
            print(f"Database error fetching CIK for ticker {ticker}: {db_err}")
            return None
        except (TypeError, IndexError) as err:
            print(f"Data processing error for ticker {ticker}: {err}")
            return None


    # Function to fetch RSS feed data
    def fetch_rss_feed(cik):
        '''
        Fetch RSS feed data
        '''
        try:
            base_url = "https://www.sec.gov/cgi-bin/browse-edgar"
            rss_url = f"{base_url}?action=getcompany&CIK={cik}&type=&dateb=&owner=include"\
                    f"&start=0&count=40&output=atom"
            headers = {
                "User-Agent": "Maitreya Moharil (maitreyamoharil@gmail.com)",
                "Referer": "https://www.sec.gov/"
            }
            response = requests.get(rss_url, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"Error fetching RSS feed for CIK {cik}: {response.status_code}")
                return []

            root = ET.fromstring(response.text)
            filings = []
            for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
                filings.append({
                "title": entry.find("{http://www.w3.org/2005/Atom}title").text,
                "link": entry.find("{http://www.w3.org/2005/Atom}link").attrib["href"],
                "updated": entry.find("{http://www.w3.org/2005/Atom}updated").text,
                "filing_type": 
                entry.find("{http://www.w3.org/2005/Atom}title").text.split(" ")[0]
                })
            return filings
        except requests.RequestException as req_err:
            print(f"Request error fetching RSS feed: {req_err}")
            return []
        except ET.ParseError as xml_err:
            print(f"XML parsing error: {xml_err}")
            return []
        except (KeyError, AttributeError) as data_err:
            print(f"Data processing error: {data_err}")
            return []


    # Function to filter filings by date
    def filter_filings_by_date_inner(filings, target_date):
        '''
        Filter filings by date
        '''
        try:
            return [filing for filing in filings if datetime.strptime(
                filing["updated"].split('.')[0].replace('Z', '+00:00'),
                '%Y-%m-%dT%H:%M:%S%z'
            ).astimezone(pytz.timezone('US/Eastern')).date() <= target_date]
        except ValueError as e:
            print(f"Error filtering filings by date: {e}")
            return []


    # Function to update tracking table and notify
    def update_tracking_table_and_notify(ticker, filings):
        '''
        Update tracking table and notify
        '''
        try:
            conn = get_db_connection()
            if not conn:
                return
            cur = conn.cursor()
            new_filings = []

            # First check if ticker exists in tracking table
            cur.execute("SELECT EXISTS(SELECT 1 FROM tracking WHERE ticker = %s)", (ticker,))
            ticker_exists = cur.fetchone()[0]

            for filing in filings:
                # Check if this filing already exists for this ticker

                # Parse and format the date correctly
                filing_date = datetime.strptime(
                    filing["updated"].split('.')[0].replace('Z', '+00:00'),
                    '%Y-%m-%dT%H:%M:%S%z'
                ).astimezone(pytz.timezone('US/Eastern')).date()

                # Update the filing dict with formatted date
                filing["updated"] = filing_date

                cur.execute("""
                    SELECT EXISTS(
                        SELECT 1 FROM tracking 
                        WHERE ticker = %s 
                        AND (
                            filing_link_1 = %s OR 
                            filing_link_2 = %s OR 
                            filing_link_3 = %s
                        )
                    )
                """, (ticker, filing["link"], filing["link"], filing["link"]))

                filing_exists = cur.fetchone()[0]

                if not filing_exists:
                    new_filings.append(filing)

            # If we have new filings, update the tracking table
            if new_filings:
                if not ticker_exists:
                    # Insert new ticker with first 3 filings (same query, updated parameters)
                    cur.execute("""
                        INSERT INTO tracking (
                            ticker, 
                            filing_title_1, filing_link_1, filing_date_1, filing_type_1,
                            filing_title_2, filing_link_2, filing_date_2, filing_type_2,
                            filing_title_3, filing_link_3, filing_date_3, filing_type_3,
                            client_id_fk
                        ) VALUES (
                            %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s
                        )
                    """, (
                        ticker,
                        new_filings[0]["title"] if len(new_filings) > 0 else None,
                        new_filings[0]["link"] if len(new_filings) > 0 else None,
                        new_filings[0]["updated"] if len(new_filings) > 0 else None,
                        new_filings[0]["filing_type"] if len(new_filings) > 0 else None,
                        new_filings[1]["title"] if len(new_filings) > 1 else None,
                        new_filings[1]["link"] if len(new_filings) > 1 else None,
                        new_filings[1]["updated"] if len(new_filings) > 1 else None,
                        new_filings[1]["filing_type"] if len(new_filings) > 1 else None,
                        new_filings[2]["title"] if len(new_filings) > 2 else None,
                        new_filings[2]["link"] if len(new_filings) > 2 else None,
                        new_filings[2]["updated"] if len(new_filings) > 2 else None,
                        new_filings[2]["filing_type"] if len(new_filings) > 2 else None,
                        CLIENT_ID
                    ))
                else:
                    # Update existing ticker with new filings
                    cur.execute("""
                        UPDATE tracking
                        SET
                            filing_title_1 = %s, filing_link_1 = %s,
                            filing_date_1 = %s, filing_type_1 = %s,
                            filing_title_2 = %s, filing_link_2 = %s,
                            filing_date_2 = %s, filing_type_2 = %s,
                            filing_title_3 = %s, filing_link_3 = %s,
                            filing_date_3 = %s, filing_type_3 = %s
                            WHERE ticker = %s
                    """, (
                        new_filings[0]["title"] if len(new_filings) > 0 else None,
                        new_filings[0]["link"] if len(new_filings) > 0 else None,
                        new_filings[0]["updated"] if len(new_filings) > 0 else None,
                        new_filings[0]["filing_type"] if len(new_filings) > 0 else None,
                        new_filings[1]["title"] if len(new_filings) > 1 else None,
                        new_filings[1]["link"] if len(new_filings) > 1 else None,
                        new_filings[1]["updated"] if len(new_filings) > 1 else None,
                        new_filings[1]["filing_type"] if len(new_filings) > 1 else None,
                        new_filings[2]["title"] if len(new_filings) > 2 else None,
                        new_filings[2]["link"] if len(new_filings) > 2 else None,
                        new_filings[2]["updated"] if len(new_filings) > 2 else None,
                        new_filings[2]["filing_type"] if len(new_filings) > 2 else None,
                        ticker
                    ))

            conn.commit()
            cur.close()
            conn.close()

            # Send email notification for new filings
            if new_filings:
                # send_email_notification(ticker, new_filings)
                update_watchlist_filings(ticker, new_filings)
                print(f"Filings Updated for {ticker}")
            elif not os.environ.get('WERKZEUG_RUN_MAIN'):  # Only print in main process
                print(f"No new filings Updated for {ticker}")

        except psycopg2.Error as db_err:
            print(f"Database error updating tracking table for ticker {ticker}: {db_err}")
        except (ValueError, TypeError) as data_err:
            print(f"Data processing error for ticker {ticker}: {data_err}")
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()


    def check_todays_filings_and_notify(ticker, target_date, filtered_filings):
        '''
        Docstring
        '''
        try:
            new_filings = []

            # Get database connection
            conn = get_db_connection()
            if not conn:
                return
            cur = conn.cursor()

            for filing in filtered_filings:
                # Convert filing["updated"] to a date object for comparison
                filing_date = datetime.strptime(
                    filing["updated"].split('.')[0].replace('Z', '+00:00'),
                    '%Y-%m-%dT%H:%M:%S%z').date()

                if filing_date == target_date:  # Compare dates
                    # Check if this filing has already been emailed
                    cur.execute(
                        "SELECT EXISTS(SELECT 1 FROM latest_filings WHERE filing_url = %s)",
                        (filing["link"],)
                    )
                    already_sent = cur.fetchone()[0]

                    if not already_sent:
                        new_filings.append(filing)

            # Send email if there are new filings
            if new_filings:
                # Add entry to notification_history table
                current_time = datetime.now().strftime('%d-%m-%Y')
                cur.execute("""
                    INSERT INTO notification_history (
                        sender_email, reciever_email, send_at, context, ticker, number_of_filings, client_id_fk
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    "maitreyamoharil@gmail.com",
                    CLIENT_EMAIL,
                    current_time,
                    "Filings Detected",
                    ticker,
                    len(new_filings),
                    CLIENT_ID
                ))

                # Record the sent emails in the email table
                for filing in new_filings:
                    if not os.environ.get('WERKZEUG_RUN_MAIN'):
                        cur.execute(
                            '''INSERT INTO latest_filings 
                            (ticker, filing_url, filing_date, filing_type, client_id_fk) 
                            VALUES (%s, %s, %s, %s, %s)''',
                            (
                            ticker,
                            filing["link"],
                            filing["updated"],
                            filing["filing_type"],
                            CLIENT_ID
                            )
                        )

                conn.commit()
                if not os.environ.get('WERKZEUG_RUN_MAIN'):  # Only print in main process
                    print(f"Found {len(new_filings)} new filings for {ticker} today")
                    send_email_notification_for_todays_filings(ticker, new_filings)
                    get_filing_list_from_dynamic_script(new_filings, ticker)
            else:
                if not os.environ.get('WERKZEUG_RUN_MAIN'):  # Only print in main process
                    print(f"No latest filings found for {ticker}")

            cur.close()
            conn.close()

        except (psycopg2.Error, ValueError, KeyError) as e:
            print(f"Error checking today's filings for ticker {ticker}: {e}")


    # Function to send email notification
    def send_email_notification_for_todays_filings(ticker, filings):
        '''
        Send email notification for todays filings
        '''
        with app.app_context():
            try:
                subject = f"Detected New SEC Filings for {ticker} that were added today"
                body = f"""
                <html>
                    <head>
                        <style>
                            .info-table {{
                                width: 100%;
                                border-collapse: collapse;
                                margin-top: 20px;
                                font-size: 14px;
                            }}
                            .info-table th, .info-table td {{
                                padding: 12px;
                                border: 1px solid #ddd;
                                text-align: center;
                            }}
                            .info-table th {{
                                background: linear-gradient(90deg, #2d3e50, #3f5a70);
                                color: white;
                                font-weight: bold;
                            }}
                            .info-table tr:nth-child(even) {{
                                background-color: #f4f7fa;
                            }}
                            .info-table tr:hover {{
                                background-color: #e1e8ef;
                            }}
                            .info-table a {{
                                color: #1a73e8;
                                text-decoration: none;
                                font-weight: bold;
                            }}
                            .info-table a:hover {{
                                text-decoration: underline;
                            }}
                            .footer {{
                                font-size: 14px;
                                color: #888;
                                margin-top: 20px;
                                text-align: center;
                            }}
                        </style>
                    </head>
                    <body>
                        <h2>New SEC Filings for {ticker} that were added today</h2>
                        <table class="info-table">
                            <tr><th>Title</th><th>Type</th><th>Link</th><th>Date</th></tr>
                            {''.join(f'''
                                <tr>
                                    <td>{filing['title']}</td>
                                    <td>{filing['filing_type']}</td>
                                    <td><a href="{filing['link']}">View Filing</a></td>
                                    <td>{filing['updated']}</td>
                                </tr>
                            ''' for filing in filings)}
                        </table>
                        <p>We will keep you updated with any changes related to this ticker. Thank you for using our tracking system!</p>
                        <div class="footer">
                            <p>Best regards,<br>Arithwise - The Solution Engine</p>
                        </div>
                    </body>
                </html>
                """

                msg = Message(subject, recipients=[CLIENT_EMAIL])
                msg.html = body
                mail.send(msg)

                print(f"Email notification sent for {ticker} that were added today.")
            except (smtplib.SMTPException, ConnectionError, ValueError) as e:
                print(f'''Error sending email notification for {ticker}
                        that were added today: {e}''')

    # Schedule the job
    schedule.every(1).minutes.do(job)

    while True:
        # Get current times
        east_now = datetime.now(pytz.timezone("US/Eastern"))
        india_now = datetime.now(pytz.timezone('Asia/Kolkata'))

        # Check if the current time is 11:45 AM EASTERN TIME
        if east_now.hour == 7 and east_now.minute == 40 and east_now.second == 0:
            if not os.environ.get('WERKZEUG_RUN_MAIN'):
                send_multiple_docx_email()

        # Check if the current time is between 10 PM and 5 AM EASTERN TIME
        if east_now.hour >= 22 or east_now.hour < 22:  # Ensure job runs between 10 PM and 5 AM
            schedule.run_pending()
        else:
            print("Schedular not working")
            time.sleep(60)  # Wait for 1 minute before checking again
        # Here will be the IF CONDITION for Parse Email Send Function
