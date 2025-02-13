"""Back end Code"""

import warnings
import xml.etree.ElementTree as ET
from datetime import datetime
import smtplib
import threading
import pytz
import psycopg2
import requests
from dateutil import parser
from flask_cors import CORS
from flask_mail import Mail, Message
from flask import Flask, jsonify, render_template, request, session
from filing_processor import get_filing_list_from_dynamic_script
from dynamic_tracking_code import dynamic_tracking


app = Flask(__name__)
CORS(app)
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
UTC = pytz.UTC

db_config = {
    "host": "localhost",
    "database": "edgar",
    "user": "postgres",
    "password": "password",
    "port": "5432",
}

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
    cur.execute("SELECT client_id, client_email, client_name FROM client_information")
    client_id, client_email, client_name = cur.fetchone()
    cur.close()
    conn.close()
    return client_id, client_email, client_name

CLIENT_ID, CLIENT_EMAIL, CLIENT_NAME = get_client_information()

@app.route("/fetch_filings", methods=["GET"])
def fetch_filings():
    """
    Fetches the first 40 filings starting from the selected date in descending order
    but sends them to the frontend in ascending order.
    """
    ticker = request.args.get("ticker")
    selected_date = request.args.get("date")  # Format: YYYY-MM-DD

    if not ticker or not selected_date:
        return jsonify({"success": False, "message": "Ticker or date is missing."}), 400

    # Fetch CIK from the database using the ticker
    result = fetch_cik_by_ticker(ticker.upper())
    if result["status"] == "error":
        return jsonify({"success": False, "message": result["message"]}), 400

    cik = result["cik"]
    filings_data = fetch_latest_filings_from_rss(cik, ticker.upper(), num_filings=100)

    # Convert selected date to a timezone-aware datetime object
    selected_datetime = datetime.strptime(selected_date, "%Y-%m-%d").replace(tzinfo=pytz.UTC)

    # Filter filings to only include those ON OR AFTER the selected date
    filtered_filings = [
        filing for filing in filings_data
        if datetime.strptime(filing["updated"], "%Y-%m-%dT%H:%M:%S%z") <= selected_datetime
    ]

    # Sort the filings in descending order (most recent first)
    filtered_filings.sort(key=lambda x: datetime.strptime(x["updated"],
                        "%Y-%m-%dT%H:%M:%S%z"))

    # Return the first 40 results in ascending order for display
    return jsonify({"success": True, "filings": list(reversed(filtered_filings[:40]))})

@app.route("/parse_filing", methods=["POST"])
def parse_filing():
    """
    Handles POST request to parse a filing row.

    Returns:
        JSON: Response containing success status and message
    """
    data = request.get_json()
    print("Received Data:", data)  # Log in terminal
    dictionary_data = data["rowdata"]
    ticker = data["ticker"]
    dictionary_data['updated'] = parser.parse(dictionary_data['updated'])
    get_filing_list_from_dynamic_script([dictionary_data], ticker)
    # Print in terminal
    print("\nParsed Row Data:", data)
    return jsonify({"success": True, "message": "Row parsed successfully!"})

@app.route("/insert_email", methods=["POST"])
def insert_email():
    """
    Handles POST request to insert a new email address into the client_information table.

    Returns:
        JSON: Response indicating success or failure of the operation
    """
    data = request.get_json()
    email = data.get("email")

    if email:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert email into the client_information table
        cursor.execute(
            "INSERT INTO client_information (client_email) VALUES (%s) RETURNING client_id_fk",
            (email,),
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True})
    return jsonify({"success": False})


@app.route("/add_to_watchlist", methods=["POST"])
def add_to_watchlist():
    """
    Handles POST request to add filings to user's watchlist in both session and database.
    Checks for existing entries

    Returns:
        JSON: Response containing success status, message, and updated watchlist
    """
    data = request.get_json()
    filings = data.get("filings", [])

    if not filings:
        return jsonify({"success": False, "message": "No filings provided"})

    # Ensure session watchlist is initialized
    if "watchlist" not in session:
        session["watchlist"] = []

    # Process each filing
    for filing in filings:
        # Store data in the PostgreSQL database
        conn = get_db_connection()
        cur = conn.cursor()

        query_check = """
        SELECT * FROM watchlist 
        WHERE ticker = %s
        """
        cur.execute(
            query_check,
            (filing["ticker"],)
        )

        existing_entry = cur.fetchone()
        print("Existing entry:", existing_entry)  # Debugging output

        if existing_entry:
            cur.close()
            conn.close()
            return jsonify(
                {
                    "success": False,
                    "message": f"Filings data already present for Ticker: {filing['ticker']}",
                }
            )

        # Add filing data to session if not already present
        if filing not in session["watchlist"]:
            session["watchlist"].append(filing)

            # Prepare SQL query to insert the filing data
            query_insert = """
            INSERT INTO watchlist (
                ticker, filing_title_1, filing_link_1, filing_date_1, filing_type_1,
                filing_title_2, filing_link_2, filing_date_2, filing_type_2,
                filing_title_3, filing_link_3, filing_date_3, filing_type_3, client_id_fk
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cur.execute(
                query_insert,
                (
                    filing["ticker"],
                    filing["filing1_title"],
                    filing["filing1_link"],
                    filing["filing1_date"],
                    filing["filing1_type"],
                    filing["filing2_title"],
                    filing["filing2_link"],
                    filing["filing2_date"],
                    filing["filing2_type"],
                    filing["filing3_title"],
                    filing["filing3_link"],
                    filing["filing3_date"],
                    filing["filing3_type"],
                    CLIENT_ID
                ),
            )
            conn.commit()

        cur.close()
        conn.close()

    session.modified = True
    return jsonify(
        {
            "success": True,
            "message": "Filings successfully added to watchlist",
            "watchlist": session["watchlist"],
        }
    )


@app.route("/get_watchlist", methods=["GET"])
def get_watchlist():
    """
    Handles GET request to retrieve user's watchlist from both session and database.

    Returns:
        JSON: Response containing watchlist data
    """
    try:
        # Get connection to database
        conn = get_db_connection()
        cur = conn.cursor()

        # Fetch watchlist data from database
        cur.execute(
            """
            SELECT ticker, filing_title_1, filing_link_1, filing_date_1, filing_type_1,
                   filing_title_2, filing_link_2, filing_date_2, filing_type_2,
                   filing_title_3, filing_link_3, filing_date_3, filing_type_3
            FROM watchlist ORDER BY order_of_display DESC
        """
        )

        # Convert database results to list of dictionaries
        db_watchlist = []
        for row in cur.fetchall():
            db_watchlist.append(
                {
                    "ticker": row[0],
                    "filing1_title": row[1],
                    "filing1_link": row[2],
                    "filing1_date": row[3],
                    "filing1_type": row[4],
                    "filing2_title": row[5],
                    "filing2_link": row[6],
                    "filing2_date": row[7],
                    "filing2_type": row[8],
                    "filing3_title": row[9],
                    "filing3_link": row[10],
                    "filing3_date": row[11],
                    "filing3_type": row[12],
                }
            )

        # Update session with database data
        session["watchlist"] = db_watchlist
        session.modified = True

        cur.close()
        conn.close()

        return jsonify({"success": True, "watchlist": db_watchlist})

    except (psycopg2.Error, ValueError, KeyError) as e:
        print(f"Error fetching watchlist: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/remove_from_watchlist", methods=["POST"])
def remove_from_watchlist():
    """
    Handles POST request to remove filings from watchlist.
    """
    data = request.get_json()
    filings = data.get("filings", [])  # Changed from filings_to_remove to filings

    if not filings or "watchlist" not in session:
        return jsonify({"success": False, "message": "Invalid request"})

    # Remove from session
    session["watchlist"] = [
        filing for filing in session["watchlist"]
        if filing not in filings
    ]
    session.modified = True

    # Remove from the database
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        for filing in filings:
            query_check = """
                DELETE FROM watchlist
                WHERE ticker = %s
                """
            cursor.execute(
                query_check,
                (filing["ticker"],)
            )

        conn.commit()
        print("Filings removed from the database")

    except (psycopg2.Error, ValueError, KeyError) as e:
        conn.rollback()
        print(f"Error removing filings: {e}")  # Add debug print
        return jsonify(
            {"success": False, "message": f"Error removing filings from database: {e}"}
        )
    finally:
        cursor.close()
        conn.close()

    return jsonify(
        {"success": True, "message": "Filings removed from the watchlist and the database"}
    )


def send_email_to_user(subject, recipient_email, ticker_details):
    """
    Sends an HTML formatted email to the specified recipient with ticker tracking details.
 
    Args:
        subject (str): Email subject line
        body (str): Plain text email body
        recipient_email (str): Recipient's email address
        ticker_details (dict): Dictionary containing ticker information
 
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Create an HTML email body with improved styling
        html_body = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    color: #333;
                    background-color: #f9f9f9;
                    padding: 20px;
                }}
                .email-container {{
                    width: 80%;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #fff;
                    border-radius: 8px;
                    box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.1);
                    text-align: center;
                }}
                h2 {{
                    color: #2d3e50;
                    margin-bottom: 10px;
                }}
                .message {{
                    font-size: 16px;
                    color: #555;
                    line-height: 1.5;
                    display: inline-block;  /* Ensures the text remains in one line */
                    margin-bottom: 20px;
                }}
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
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <h2>Tracking Started for Ticker: {ticker_details['ticker']}</h2>
                <div class="message">
                    Dear User, Tracking for ticker <strong>{ticker_details['ticker']}</strong> has been successfully started.
                </div>
               
                <table class="info-table">
                    <thead>
                        <tr>
                            <th>Ticker</th>
                            <th>Filing 1</th>
                            <th>Filing 2</th>
                            <th>Filing 3</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td rowspan="4"><strong>{ticker_details['ticker']}</strong></td>
                            <td><strong>Title:</strong> {ticker_details['filing_title_1'] or 'N/A'}</td>
                            <td><strong>Title:</strong> {ticker_details['filing_title_2'] or 'N/A'}</td>
                            <td><strong>Title:</strong> {ticker_details['filing_title_3'] or 'N/A'}</td>
                        </tr>
                        <tr>
                            <td><strong>Type:</strong> {ticker_details['filing_type_1'] or 'N/A'}</td>
                            <td><strong>Type:</strong> {ticker_details['filing_type_2'] or 'N/A'}</td>
                            <td><strong>Type:</strong> {ticker_details['filing_type_3'] or 'N/A'}</td>
                        </tr>
                        <tr>
                            <td><strong>Date:</strong> {ticker_details['filing_date_1'] or 'N/A'}</td>
                            <td><strong>Date:</strong> {ticker_details['filing_date_2'] or 'N/A'}</td>
                            <td><strong>Date:</strong> {ticker_details['filing_date_3'] or 'N/A'}</td>
                        </tr>
                        <tr>
                            <td><a href="{ticker_details['filing_link_1']}" target="_blank">View Filing</a></td>
                            <td><a href="{ticker_details['filing_link_2']}" target="_blank">View Filing</a></td>
                            <td><a href="{ticker_details['filing_link_3']}" target="_blank">View Filing</a></td>
                        </tr>
                    </tbody>
                </table>
 
                <p>We will keep you updated with any changes related to this ticker. Thank you for using our tracking system!</p>
               
                <div class="footer">
                    <p>Best regards,<br>Arithwise - The Solution Engine</p>
                </div>
            </div>
        </body>
        </html>
        """
        # Send the HTML email
        msg = Message(subject, recipients=[recipient_email])
        msg.html = html_body
        mail.send(msg)
        print("Tracking Started Email sent successfully!")
        return True

    except (smtplib.SMTPException, ConnectionError, ValueError) as e:
        print(f"Failed to send email: {e}")
        return False


def format_to_timestamp(date_string):
    """
    Converts a date string to timestamp format.

    Args:
        date_string (str): Date string to convert

    Returns:
        str: Formatted timestamp string or None if conversion fails
    """
    if not date_string or date_string.lower() == "undefined":
        print(f"Invalid or undefined date: {date_string}")
        return None
    try:
        date_obj = datetime.fromisoformat(date_string)
        return date_obj.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        print(f"Error parsing date: {date_string}, {e}")
        return None


@app.route("/get_emails", methods=["GET"])
def get_emails():
    """
    Handles GET request to retrieve all email addresses from client_information table.

    Returns:
        JSON: Response containing list of email addresses
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to fetch all emails
    cursor.execute("SELECT c_email FROM client_information;")
    emails = cursor.fetchall()

    cursor.close()
    conn.close()

    # Return emails as a JSON response
    return jsonify({"emails": [email[0] for email in emails]})


# Function to fetch CIK by ticker from the database
def fetch_cik_by_ticker(ticker):
    """
    Retrieves CIK number for a given stock ticker from database.

    Args:
        ticker (str): Stock ticker symbol

    Returns:
        dict: Dictionary containing CIK (if found) and status message
    """
    if ticker.strip() == '':
        return {"cik": None, "status": "error",
                "message": "Empty or blank spaces can't be used as a ticker"}
    conn = get_db_connection()
    cur = conn.cursor()

    # Query to get CIK based on the ticker
    cur.execute("SELECT cik FROM public.company_list WHERE ticker = %s;", (ticker,))
    result = cur.fetchone()

    cur.close()
    conn.close()

    if result:
        return {"cik": result[0], "status": "success"}
    return {"cik": None, "status": "error", "message": "Invalid Ticker"}


@app.route("/get_ticker_suggestions", methods=["GET"])
def get_ticker_suggestions():
    """
    Handles GET request to provide autocomplete suggestions for ticker search.

    Returns:
        JSON: Response containing list of ticker suggestions
    """
    search_term = request.args.get(
        "term", ""
    ).strip()  # Get the search term from the query string
    if not search_term:
        return jsonify([])  # Return an empty list if no search term

    conn = get_db_connection()
    cur = conn.cursor()
    query = """
        SELECT ticker, ticker_and_company
        FROM public.company_list
        WHERE ticker_and_company ILIKE %s
        LIMIT 10;  -- Limit the number of suggestions
    """
    cur.execute(query, (f"%{search_term}%",))
    suggestions = [{"ticker": row[0], "display": row[1]} for row in cur.fetchall()]
    cur.close()
    conn.close()

    return jsonify(suggestions)


# Function to fetch filings from SEC RSS feed based on CIK
def fetch_latest_filings_from_rss(cik, ticker, num_filings = 40):
    """
    Fetches latest SEC filings for a company from SEC's RSS feed.

    Args:
        cik (str): Company's CIK number
        ticker (str): Stock ticker symbol
        num_filings (int): Number of filings to fetch (default: 40)

    Returns:
        list: List of filing dictionaries containing filing details
    """
    filings = []
    start = 0
    while len(filings) < num_filings:
        rss_url = f"""
        https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}
        &type=&dateb=&owner=include&start={start}&count=40&output=atom"""
        headers = {
            "User-Agent": "Neesha Diwakar <neeshadiwakar@gmail.com> Mozilla/5.0",
            "Referer": "https://www.sec.gov/",
        }
        response = requests.get(rss_url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(
                f"Error fetching data for CIK {cik}. HTTP Status Code: {response.status_code}"
            )
            return []

        root = ET.fromstring(response.text)
        print(
            f"Fetched {len(root.findall('{http://www.w3.org/2005/Atom}entry'))} entries"
        )

        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            filing = {}
            filing["title"] = entry.find("{http://www.w3.org/2005/Atom}title").text
            filing["link"] = entry.find("{http://www.w3.org/2005/Atom}link").attrib[
                "href"
            ]
            filing["updated"] = entry.find("{http://www.w3.org/2005/Atom}updated").text
            filing["filing_type"] = entry.find(
                "{http://www.w3.org/2005/Atom}title"
            ).text.split(" ")[0]
            filing["ticker"] = ticker  # Add ticker to filing
            filings.append(filing)

        start += 40  # Increase the starting index for the next set of filings
        if len(root.findall("{http://www.w3.org/2005/Atom}entry")) < 40:
            break

    print(f"Total filings fetched: {len(filings)}")
    return filings[:num_filings]


# Function to filter filings by date
def filter_filings_by_date(filings, selected_date):
    """
    Filters list of filings by date.

    Args:
        filings (list): List of filing dictionaries
        selected_date (str): Date string to filter by

    Returns:
        list: Filtered list of filings
    """
    filtered_filings = []
    selected_date = datetime.strptime(selected_date, "%Y-%m-%d")
    selected_date = pytz.timezone("UTC").localize(selected_date)
    for filing in filings:
        filing_date = datetime.strptime(
            filing["updated"], "%Y-%m-%dT%H:%M:%S%z"
        ).replace(tzinfo=pytz.UTC)
        if filing_date.date() <= selected_date.date():  # Compare only date part
            filtered_filings.append(filing)
    return filtered_filings[:3]  # Return only the first 3 filings


# Function to filter filings by type
def filter_filings_by_type(filings, filing_type):
    """
    Filters list of filings by filing type.

    Args:
        filings (list): List of filing dictionaries
        filing_type (str): Filing type to filter by

    Returns:
        list: Filtered list of filings
    """
    if not filing_type:
        return filings
    return [filing for filing in filings if filing["filing_type"] == filing_type]


@app.route("/", methods=["GET", "POST"])
def index():
    """
    Handles main route for both GET and POST requests.
    Manages filing search, filtering, and display functionality.
    """
    filings = []  # Initialize the list of filings
    selected_date = request.form.get("date_picker")
    date_toggle = request.form.get("dateToggle") == "on"  # Get the toggle state

    # Store date in session to persist it
    if selected_date:
        session['selected_date'] = selected_date
    elif date_toggle and 'selected_date' in session:
        selected_date = session['selected_date']

    selected_filing_type = request.form.get("filing_type")
    ticker = request.form.get("ticker")
    error_message = None

    # Clear filings data from session after every refresh
    session.pop("filings_data", None)

    if request.method == "POST":
        # Fetch CIK from the database using the ticker
        if ticker:
            result = fetch_cik_by_ticker(ticker.upper())
            if result["status"] == "error":
                error_message = result["message"]
                cik = None
            else:
                cik = result["cik"]
        else:
            cik = None

        if cik:
            filings_data = fetch_latest_filings_from_rss(cik, ticker.upper(), num_filings=100)

            # Check if any filings were found
            if not filings_data:
                error_message = "No Filings Found"
            else:
                # Only apply date filter if date_toggle is True and selected_date exists
                if date_toggle and selected_date:
                    filings_data = filter_filings_by_date(filings_data, selected_date)

                filings_data = filter_filings_by_type(filings_data, selected_filing_type)

                # Check if any filings remain after filtering
                if not filings_data:
                    error_message = "No filings Found"
                else:
                    # Group filings by ticker
                    grouped_filings = {}
                    for filing in filings_data:
                        filing_ticker = filing.get("ticker")
                        if filing_ticker:
                            if filing_ticker not in grouped_filings:
                                grouped_filings[filing_ticker] = []
                            grouped_filings[filing_ticker].append(filing)

                    # Ensure we only show up to 3 filings per ticker
                    new_filings = []
                    for filing_ticker, filing_set in grouped_filings.items():
                        new_filings.append({
                            "ticker": filing_ticker,
                            "filings": filing_set[:3],
                        })

                    session["filings_data"] = new_filings

    # Pass the filings data, form values, and error message back to the template
    filings = session.get("filings_data", [])

    return render_template(
        "index.html",
        filings=filings,
        selected_date=selected_date,
        date_toggle=date_toggle,
        selected_filing_type=selected_filing_type,
        ticker=ticker,
        error_message=error_message,
        CLIENT_EMAIL=CLIENT_EMAIL,
        CLIENT_NAME=CLIENT_NAME
    )

@app.route("/toggle_tracking", methods=["POST"])
def toggle_tracking():
    '''Toggle tracking status for a filing'''
    data = request.get_json()
    ticker = data.get("ticker")
    recipient_email = CLIENT_EMAIL

    if not ticker:
        return jsonify({"success": False, "message": "Ticker not provided"}), 400

    # Helper function to convert string 'null' to None
    def clean_value(value):
        if value == 'null' or value == '':
            return None
        return value

    # Clean the input data
    cleaned_data = {
        'filing_title_1': clean_value(data.get('filing_title_1')),
        'filing_link_1': clean_value(data.get('filing_link_1')),
        'filing_date_1': clean_value(data.get('filing_date_1')),
        'filing_type_1': clean_value(data.get('filing_type_1')),
        'filing_title_2': clean_value(data.get('filing_title_2')),
        'filing_link_2': clean_value(data.get('filing_link_2')),
        'filing_date_2': clean_value(data.get('filing_date_2')),
        'filing_type_2': clean_value(data.get('filing_type_2')),
        'filing_title_3': clean_value(data.get('filing_title_3')),
        'filing_link_3': clean_value(data.get('filing_link_3')),
        'filing_date_3': clean_value(data.get('filing_date_3')),
        'filing_type_3': clean_value(data.get('filing_type_3'))
    }

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # First, check if this exact record exists
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM tracking 
                WHERE ticker = %s 
            )
        """, (
            ticker,
        ))

        record_exists = cur.fetchone()[0]

        if record_exists:
            # Delete the record if it exists
            cur.execute("""
                DELETE FROM tracking 
                WHERE ticker = %s 
            """, (
                ticker,
            ))

            cur.execute("""SELECT EXISTS (
                SELECT 1 FROM latest_filings WHERE ticker = %s
            )""", (ticker,))
            filing_log_exists = cur.fetchone()[0]

            if filing_log_exists:
                cur.execute("""
                DELETE FROM latest_filings WHERE ticker = %s
                """, (ticker,))

            conn.commit()

            return jsonify({
                "success": True,
                "message": "Tracking has been stopped",
                "status": "removed"
            })
        else:
            # Insert new record if it doesn't exist
            cur.execute("""
                INSERT INTO tracking (
                    ticker, filing_title_1, filing_link_1, filing_date_1, filing_type_1,
                    filing_title_2, filing_link_2, filing_date_2, filing_type_2,
                    filing_title_3, filing_link_3, filing_date_3, filing_type_3, client_id_fk
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                ticker,
                cleaned_data['filing_title_1'], cleaned_data['filing_link_1'],
                cleaned_data['filing_date_1'], cleaned_data['filing_type_1'],
                cleaned_data['filing_title_2'], cleaned_data['filing_link_2'],
                cleaned_data['filing_date_2'], cleaned_data['filing_type_2'],
                cleaned_data['filing_title_3'], cleaned_data['filing_link_3'],
                cleaned_data['filing_date_3'], cleaned_data['filing_type_3'],
                CLIENT_ID
            ))

            # Send email notification for new tracking
            ticker_details = {
                "ticker": ticker,
                "filing_title_1": cleaned_data['filing_title_1'] or "N/A",
                "filing_link_1": cleaned_data['filing_link_1'] or "#",
                "filing_date_1": cleaned_data['filing_date_1'] or "N/A",
                "filing_type_1": cleaned_data['filing_type_1'] or "N/A",
                "filing_title_2": cleaned_data['filing_title_2'] or "N/A",
                "filing_link_2": cleaned_data['filing_link_2'] or "#",
                "filing_date_2": cleaned_data['filing_date_2'] or "N/A",
                "filing_type_2": cleaned_data['filing_type_2'] or "N/A",
                "filing_title_3": cleaned_data['filing_title_3'] or "N/A",
                "filing_link_3": cleaned_data['filing_link_3'] or "#",
                "filing_date_3": cleaned_data['filing_date_3'] or "N/A",
                "filing_type_3": cleaned_data['filing_type_3'] or "N/A"
            }

            # Calculate number of filings using list comprehension
            number_of_filings = len([i for i in range(1, 4) if not all(
                ticker_details[f"filing_{field}_{i}"] in ["N/A", "#"]
                for field in ["title", "date", "type", "link"]
            )])

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
                "Tracking Started",
                ticker,
                number_of_filings,
                CLIENT_ID
            ))

            conn.commit()

            email_sent = send_email_to_user(
                subject="Tracking Started",
                recipient_email=recipient_email,
                ticker_details=ticker_details
            )

            return jsonify({
                "success": True,
                "message": "Tracking has been started" + 
                (f" and Email has been sent to {recipient_email}" if email_sent else ""),
                "status": "added"
            })

    except (psycopg2.Error, ValueError, KeyError) as e:
        print(f"Error: {e}")
        return jsonify({"success": False, "message": f"Error toggling tracking: {e}"}), 500
    finally:
        cur.close()
        conn.close()


@app.route("/check_tracking", methods=["POST"])
def check_tracking():
    '''Check if a filing is being tracked'''
    data = request.get_json()
    ticker = data.get("ticker")

    if not ticker:
        return jsonify({"success": False, "message": "Ticker not provided"}), 400

    # Helper function to convert string 'null' to None
    def clean_value(value):
        if value == 'null' or value == '':
            return None
        return value

    # Clean the input data
    cleaned_data = {
        'filing_title_1': clean_value(data.get('filing_title_1')),
        'filing_link_1': clean_value(data.get('filing_link_1')),
        'filing_date_1': clean_value(data.get('filing_date_1')),
        'filing_type_1': clean_value(data.get('filing_type_1')),
        'filing_title_2': clean_value(data.get('filing_title_2')),
        'filing_link_2': clean_value(data.get('filing_link_2')),
        'filing_date_2': clean_value(data.get('filing_date_2')),
        'filing_type_2': clean_value(data.get('filing_type_2')),
        'filing_title_3': clean_value(data.get('filing_title_3')),
        'filing_link_3': clean_value(data.get('filing_link_3')),
        'filing_date_3': clean_value(data.get('filing_date_3')),
        'filing_type_3': clean_value(data.get('filing_type_3'))
    }

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if this exact record exists
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM tracking 
                WHERE ticker = %s 
                AND (filing_title_1 = %s OR (filing_title_1 IS NULL AND %s IS NULL))
                AND (filing_link_1 = %s OR (filing_link_1 IS NULL AND %s IS NULL))
                AND (filing_date_1 = %s OR (filing_date_1 IS NULL AND %s IS NULL))
                AND (filing_type_1 = %s OR (filing_type_1 IS NULL AND %s IS NULL))
                AND (filing_title_2 = %s OR (filing_title_2 IS NULL AND %s IS NULL))
                AND (filing_link_2 = %s OR (filing_link_2 IS NULL AND %s IS NULL))
                AND (filing_date_2 = %s OR (filing_date_2 IS NULL AND %s IS NULL))
                AND (filing_type_2 = %s OR (filing_type_2 IS NULL AND %s IS NULL))
                AND (filing_title_3 = %s OR (filing_title_3 IS NULL AND %s IS NULL))
                AND (filing_link_3 = %s OR (filing_link_3 IS NULL AND %s IS NULL))
                AND (filing_date_3 = %s OR (filing_date_3 IS NULL AND %s IS NULL))
                AND (filing_type_3 = %s OR (filing_type_3 IS NULL AND %s IS NULL))
            )
        """, (
            ticker,
            cleaned_data['filing_title_1'], cleaned_data['filing_title_1'],
            cleaned_data['filing_link_1'], cleaned_data['filing_link_1'],
            cleaned_data['filing_date_1'], cleaned_data['filing_date_1'],
            cleaned_data['filing_type_1'], cleaned_data['filing_type_1'],
            cleaned_data['filing_title_2'], cleaned_data['filing_title_2'],
            cleaned_data['filing_link_2'], cleaned_data['filing_link_2'],
            cleaned_data['filing_date_2'], cleaned_data['filing_date_2'],
            cleaned_data['filing_type_2'], cleaned_data['filing_type_2'],
            cleaned_data['filing_title_3'], cleaned_data['filing_title_3'],
            cleaned_data['filing_link_3'], cleaned_data['filing_link_3'],
            cleaned_data['filing_date_3'], cleaned_data['filing_date_3'],
            cleaned_data['filing_type_3'], cleaned_data['filing_type_3']
        ))

        is_tracked = cur.fetchone()[0]

        return jsonify({
            "success": True,
            "isTracked": is_tracked
        })

    except (psycopg2.Error, ValueError, KeyError) as e:
        print(f"Error: {e}")
        return jsonify({"success": False, "message": f"Error checking tracking status: {e}"}), 500
    finally:
        cur.close()
        conn.close()

@app.route("/ticker/<ticker>")
def ticker_filings(ticker):
    """Fetch latest 40 filings for the given ticker and render a page."""
    result = fetch_cik_by_ticker(ticker.upper())
    if result["status"] == "error":
        return render_template("filings.html", error_message=result["message"], ticker=ticker)

    cik = result["cik"]
    filings = fetch_latest_filings_from_rss(cik, ticker.upper(), num_filings=40)

    return render_template("filings.html", filings=filings, ticker=ticker)


if __name__ == "__main__":
    # Run the Python script in a separate thread
    script_thread = threading.Thread(target = dynamic_tracking)
    script_thread.daemon = True  # Ensures thread closes when the main program exits
    script_thread.start()

    # Use PendingDeprecationWarning from the warnings module
    warnings.warn("This feature is pending deprecation", PendingDeprecationWarning)

    app.run(debug=True)
