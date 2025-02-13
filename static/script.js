function showModal(message, callback, showCancel = false) {
    const modal = document.getElementById("custom-modal");
    const messageEl = document.getElementById("modal-message");
    const okButton = document.getElementById("modal-ok");
    const cancelButton = document.getElementById("modal-cancel");

    messageEl.innerText = message;
    cancelButton.style.display = showCancel ? "inline-block" : "none";
    modal.style.display = "block";

    okButton.onclick = () => {
    modal.style.display = "none";
    if (callback) callback(true);
    };

    cancelButton.onclick = () => {
    modal.style.display = "none";
    if (callback) callback(false);
    };

    window.onclick = (event) => {
    if (event.target === modal) {
        modal.style.display = "none";
        if (callback) callback(false);
    }
    };
}
    // Example usage: Replace alert or confirm
    function customAlert(message) {
    showModal(message, null, false);
    }

    function customConfirm(message, callback) {
    showModal(message, callback, true);
}

// const loadingSpinnerURL = "{{ url_for('static', filename='images/db.gif') }}";
const loadingSpinnerURL = document.getElementById('spinner').dataset.loadingUrl;

document.addEventListener('DOMContentLoaded', function() {
    const dateToggle = document.getElementById('dateToggle');
    const dateInput = document.getElementById('date_picker');

    // Function to get current date in YYYY-MM-DD format
    function getCurrentDate() {
        const today = new Date();
        return today.toISOString().split('T')[0];
    }

    // Initialize the date picker state based on existing value
    if (dateInput.value) {
        dateToggle.checked = true;
        dateInput.disabled = false;
    } else if (dateToggle.checked) {
        // If toggle is checked but no date is set, use current date
        dateInput.value = getCurrentDate();
        dateInput.disabled = false;
    }

    // Handle date toggle
    dateToggle.addEventListener('change', function() {
        if (dateToggle.checked) {
            dateInput.disabled = false;
            // Only set current date if there's no existing value
            if (!dateInput.value) {
                dateInput.value = getCurrentDate();
            }
            dateInput.focus();
        } else {
            dateInput.disabled = true;
            dateInput.value = '';
        }
    });
});

document.getElementById('ticker').addEventListener('input', function () {
    const query = this.value;
    if (query.length < 2) {
        document.getElementById('suggestions').innerHTML = '';
        return;
    }

    fetch(`/get_ticker_suggestions?term=${query}`)
        .then(response => response.json())
        .then(data => {
            const suggestions = document.getElementById('suggestions');
            suggestions.innerHTML = '';
            data.forEach(item => {
                const suggestionItem = document.createElement('li');
                suggestionItem.textContent = item.display; // Show ticker_and_company
                suggestionItem.dataset.ticker = item.ticker; // Store ticker as a data attribute
                suggestionItem.addEventListener('click', function () {
                    document.getElementById('ticker').value = this.dataset.ticker; // Set only ticker in input
                    suggestions.innerHTML = ''; // Clear suggestions
                });
                suggestions.appendChild(suggestionItem);
            });
        })
        .catch(error => console.error('Error fetching suggestions:', error));
});

document.querySelectorAll('.watchlist-button').forEach(function (button) {
    button.addEventListener('click', function () {
        const email = document.getElementById('emailInput').value;
        if (!email) {
            customAlert('Please enter or select an email before adding to the watchlist.');
            return;
        }

        const filingsData = [
            {
                filing1_title: button.getAttribute('data-filing1-title') || null,
                filing1_type: button.getAttribute('data-filing1-type') || null,
                filing1_date: button.getAttribute('data-filing1-date') || null,
                filing1_link: button.getAttribute('data-filing1-link') || null,
                ticker: button.getAttribute('data-ticker') || null,
                filing2_title: button.getAttribute('data-filing2-title') || null,
                filing2_type: button.getAttribute('data-filing2-type') || null,
                filing2_date: button.getAttribute('data-filing2-date') || null,
                filing2_link: button.getAttribute('data-filing2-link') || null,
                filing3_title: button.getAttribute('data-filing3-title') || null,
                filing3_type: button.getAttribute('data-filing3-type') || null,
                filing3_date: button.getAttribute('data-filing3-date') || null,
                filing3_link: button.getAttribute('data-filing3-link') || null,
            },
        ];

        fetch('/add_to_watchlist', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email: email, filings: filingsData }),
        })
        .then((response) => response.json())
        .then((data) => {
            if (data.success) {
                customAlert('Added to Watchlist successfully!');
                loadWatchlist();
            } else {
                customAlert(`${data.message}`);
            }
        })
        .catch((error) => {
            console.error('Error:', error);
        });
    });
});

// Function to check tracking status and update button
function checkAndUpdateTrackingStatus(button) {
    const rowData = {
        ticker: button.dataset.ticker,
        filing_title_1: button.dataset.filing1Title,
        filing_link_1: button.dataset.filing1Link,
        filing_date_1: button.dataset.filing1Date,
        filing_type_1: button.dataset.filing1Type,
        filing_title_2: button.dataset.filing2Title,
        filing_link_2: button.dataset.filing2Link,
        filing_date_2: button.dataset.filing2Date,
        filing_type_2: button.dataset.filing2Type,
        filing_title_3: button.dataset.filing3Title,
        filing_link_3: button.dataset.filing3Link,
        filing_date_3: button.dataset.filing3Date,
        filing_type_3: button.dataset.filing3Type
    };

    fetch('/check_tracking', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rowData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            
        if (data.isTracked) {
        button.textContent = 'Stop';
        button.classList.add('tracking-active');
        button.style.background = 'linear-gradient(90deg, #28a745, #3fdd8b)'; // Green color for tracked state
        button.style.color = 'white'; // White text color for contrast
        }

        else {
        button.textContent = 'Start';
        button.classList.remove('tracking-active');
        button.style.background = ''; // Reset to original color
        button.style.color = ''; // Reset text color
        }
        }
    })
    .catch(error => console.error('Error checking tracking status:', error));
}

// Modify your loadWatchlist function to include the tracking status check
function loadWatchlist() {
    fetch('/get_watchlist', {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        },
    })
    .then((response) => response.json())
    .then((data) => {
        const table = document.querySelector('.watchlist-table tbody');
        table.innerHTML = ''; // Clear existing rows

        if (data.success && data.watchlist.length > 0) {
            data.watchlist.forEach((filing) => {
                const newRow = document.createElement('tr');
                newRow.setAttribute('data-ticker', filing.ticker); // Store the ticker on the row
                newRow.innerHTML = `
                    <td style="display: flex; align-items: center; gap: 10px;">
                         <button class="ticker-button" data-ticker="${filing.ticker}">

                            ${filing.ticker}

                        </button>
                        <input type="checkbox" class="row-checkbox" data-ticker="${filing.ticker}" style="display: none;">
                    </td>

                    <td>
                        ${filing.filing1_title || filing.filing1_type || filing.filing1_date || filing.filing1_link ? `
                            <strong>Title:</strong> ${filing.filing1_title || 'N/A'}<br>
                            <strong>Link:</strong> ${filing.filing1_link ? `<a href="${filing.filing1_link}" target="_blank">View Filing</a>` : 'N/A'}<br>
                            <strong>Date:</strong> ${filing.filing1_date || 'N/A'}<br>
                            <strong>Filing Type:</strong> ${filing.filing1_type || 'N/A'}
                        ` : 'N/A'}
                    </td>
                    <td>
                        ${filing.filing2_title || filing.filing2_type || filing.filing2_date || filing.filing2_link ? `
                            <strong>Title:</strong> ${filing.filing2_title || 'N/A'}<br>
                            <strong>Link:</strong> ${filing.filing2_link ? `<a href="${filing.filing2_link}" target="_blank">View Filing</a>` : 'N/A'}<br>
                            <strong>Date:</strong> ${filing.filing2_date || 'N/A'}<br>
                            <strong>Filing Type:</strong> ${filing.filing2_type || 'N/A'}
                        ` : 'N/A'}
                    </td>
                    <td>
                        ${filing.filing3_title || filing.filing3_type || filing.filing3_date || filing.filing3_link ? `
                            <strong>Title:</strong> ${filing.filing3_title || 'N/A'}<br>
                            <strong>Link:</strong> ${filing.filing3_link ? `<a href="${filing.filing3_link}" target="_blank">View Filing</a>` : 'N/A'}<br>
                            <strong>Date:</strong> ${filing.filing3_date || 'N/A'}<br>
                            <strong>Filing Type:</strong> ${filing.filing3_type || 'N/A'}
                        ` : 'N/A'}
                    </td>
                    <td>
                        <button class="track-watchlist-button"
                            data-ticker="${filing.ticker}"
                            data-filing1-title="${filing.filing1_title || null}"
                            data-filing1-link="${filing.filing1_link || null}"
                            data-filing1-date="${filing.filing1_date || null}"
                            data-filing1-type="${filing.filing1_type || null}"
                            data-filing2-title="${filing.filing2_title || null}"
                            data-filing2-link="${filing.filing2_link || null}"
                            data-filing2-date="${filing.filing2_date || null}"
                            data-filing2-type="${filing.filing2_type || null}"
                            data-filing3-title="${filing.filing3_title || null}"
                            data-filing3-link="${filing.filing3_link || null}"
                            data-filing3-date="${filing.filing3_date || null}"
                            data-filing3-type="${filing.filing3_type || null}">
                            Start
                            <span class="button-text">Start</span>
                            <span class="loading-icon" style="display: none;">
                                <img src="{{ url_for('static', filename='images/loading.gif') }}" alt="Loading" width="20">
                            </span>
                        </button>
                    </td>
                `;
                table.appendChild(newRow);

                // After creating the track-watchlist-button:
                const trackButton = newRow.querySelector('.track-watchlist-button');
                if (trackButton) {
                    checkAndUpdateTrackingStatus(trackButton);
                }
            });
        } else {
            table.innerHTML = '<tr><td colspan="5">No items in watchlist</td></tr>';
        }
    })
    .catch((error) => {
        console.error('Error fetching watchlist:', error);
    });
}

// Call loadWatchlist when the page loads
document.addEventListener('DOMContentLoaded', function() {
    loadWatchlist();
});

// Enable and show checkboxes on "Remove from Watchlist"
document.addEventListener('DOMContentLoaded', () => {
    const removeSelectedButton = document.getElementById('removeSelectedButton');

    removeSelectedButton.addEventListener('click', () => {
        // First check if watchlist is empty by looking at the table rows
        const tableRows = document.querySelectorAll('.watchlist-table tbody tr');
        const isWatchlistEmpty = tableRows.length === 0 || 
            (tableRows.length === 1 && tableRows[0].querySelector('td[colspan="5"]')); // Check for "No items" row

        if (isWatchlistEmpty) {
            customAlert('Watchlist is empty');
            return;
        }

        const checkboxes = document.querySelectorAll('.row-checkbox');
        
        // Toggle checkbox visibility
        if (checkboxes[0]?.style.display === 'none') {
            checkboxes.forEach((checkbox) => {
                checkbox.style.display = ''; // Show the checkbox
                checkbox.disabled = false;
            });
            removeSelectedButton.textContent = "Confirm Remove";
        } else {
            const selectedCheckboxes = Array.from(checkboxes).filter((checkbox) => checkbox.checked);
            
            if (selectedCheckboxes.length === 0) {
                customAlert('Please select at least one item to remove.');
                return;
            }

            const email = document.getElementById('emailInput').value;
            const filingsToRemove = selectedCheckboxes.map((checkbox) => {
                const row = checkbox.closest('tr');
                const trackButton = row.querySelector('.track-watchlist-button');
                
                // Create filing object with null check for each property
                return {
                    ticker: trackButton.dataset.ticker || null,
                    filing1_title: trackButton.dataset.filing1Title === "null" ? null : trackButton.dataset.filing1Title,
                    filing1_link: trackButton.dataset.filing1Link === "null" ? null : trackButton.dataset.filing1Link,
                    filing1_date: trackButton.dataset.filing1Date === "null" ? null : trackButton.dataset.filing1Date,
                    filing1_type: trackButton.dataset.filing1Type === "null" ? null : trackButton.dataset.filing1Type,
                    filing2_title: trackButton.dataset.filing2Title === "null" ? null : trackButton.dataset.filing2Title,
                    filing2_link: trackButton.dataset.filing2Link === "null" ? null : trackButton.dataset.filing2Link,
                    filing2_date: trackButton.dataset.filing2Date === "null" ? null : trackButton.dataset.filing2Date,
                    filing2_type: trackButton.dataset.filing2Type === "null" ? null : trackButton.dataset.filing2Type,
                    filing3_title: trackButton.dataset.filing3Title === "null" ? null : trackButton.dataset.filing3Title,
                    filing3_link: trackButton.dataset.filing3Link === "null" ? null : trackButton.dataset.filing3Link,
                    filing3_date: trackButton.dataset.filing3Date === "null" ? null : trackButton.dataset.filing3Date,
                    filing3_type: trackButton.dataset.filing3Type === "null" ? null : trackButton.dataset.filing3Type
                };
            });

            fetch('/remove_from_watchlist', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email: email,
                    filings: filingsToRemove  // Changed from tickers to complete filing data
                }),
            })
            .then((response) => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then((result) => {
                if (result.success) {
                    // Remove the rows from the table
                    filingsToRemove.forEach((filing) => {
                        const row = document.querySelector(`tr[data-ticker="${filing.ticker}"]`);
                        if (row) row.remove();
                    });

                    // Reset the checkboxes and button
                    checkboxes.forEach((checkbox) => {
                        checkbox.style.display = 'none';
                        checkbox.disabled = true;
                    });
                    removeSelectedButton.textContent = "Remove from Watchlist";
                    
                    customAlert('Successfully removed selected items from watchlist');
                } else {
                    customAlert(result.message || 'Failed to remove items from watchlist');
                }
            })
            .catch((error) => {
                console.error('Error removing items:', error);
                customAlert('An error occurred while removing items from watchlist');
            });
        }
    });
});

document.addEventListener('DOMContentLoaded', function () {
    loadWatchlist(); // Load the watchlist when the page is ready

    // Event delegation to handle dynamically added "Remove" buttons
    document.querySelector('.watchlist-table').addEventListener('click', function (event) {
        if (event.target && event.target.classList.contains('remove-watchlist-button')) {
            const filingTitle = event.target.getAttribute('data-filing-title');
            const ticker = event.target.getAttribute('data-ticker');
            const filing = {
                filing_title: filingTitle,
                ticker: ticker,
            };

            console.log('Removing filing:', filing);

            fetch('/remove_from_watchlist', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ filing: filing }),
            })
            .then((response) => response.json())
            .then((data) => {
                if (data.success) {
                    loadWatchlist(); // Reload the watchlist to reflect changes
                } else {
                    customAlert('Failed to remove from Watchlist');
                }
            })
            .catch((error) => {
                console.error('Error:', error);
            });
        }
    });
});

document.addEventListener('DOMContentLoaded', function () {
    document.querySelector('.watchlist-table').addEventListener('click', function (event) {
        if (event.target && event.target.classList.contains('track-watchlist-button')) {
            const button = event.target;
            const isCurrentlyTracking = button.textContent === 'Stop';
 
            // If currently tracking, show confirmation dialog
            if (isCurrentlyTracking) {
                customConfirm('Are you sure you want to stop tracking this ticker?', function (confirmed) {
                    if (!confirmed) return; // Exit if user cancels
 
                    toggleTracking(button);
                });
            } else {
                toggleTracking(button);
            }
        }
    });
});

// Function to toggle tracking
function toggleTracking(button) {
    const originalButtonHTML = button.innerHTML;
    const loadingSpinnerHTML = `<img src="${loadingSpinnerURL}" alt="Loading..." style="width: 60px; height: 40px;">`;
 
    button.innerHTML = loadingSpinnerHTML;
    button.disabled = true;
 
    const rowData = {
        ticker: button.dataset.ticker,
        filing_title_1: button.dataset.filing1Title,
        filing_link_1: button.dataset.filing1Link,
        filing_date_1: button.dataset.filing1Date,
        filing_type_1: button.dataset.filing1Type,
        filing_title_2: button.dataset.filing2Title,
        filing_link_2: button.dataset.filing2Link,
        filing_date_2: button.dataset.filing2Date,
        filing_type_2: button.dataset.filing2Type,
        filing_title_3: button.dataset.filing3Title,
        filing_link_3: button.dataset.filing3Link,
        filing_date_3: button.dataset.filing3Date,
        filing_type_3: button.dataset.filing3Type,
        email: document.getElementById('emailInput').value,
    };
 
    fetch('/toggle_tracking', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rowData),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (data.status === 'added') {
                button.textContent = 'Stop';
                button.classList.add('tracking-active');
                button.style.background = 'linear-gradient(90deg, #28a745, #3fdd8b)';
                button.style.color = 'white';
            } else if (data.status === 'removed') {
                button.textContent = 'Start';
                button.classList.remove('tracking-active');
                button.style.background = '';
                button.style.color = '';
            }
            customAlert(data.message);
        } else {
            customAlert(`${data.message}`);
            button.innerHTML = originalButtonHTML;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        customAlert('An error occurred while toggling tracking.');
        button.innerHTML = originalButtonHTML;
    })
    .finally(() => {
        button.disabled = false;
    });
}

document.addEventListener('DOMContentLoaded', function () {
    const emailButton = document.getElementById('insertEmailButton');

    emailButton.addEventListener('click', function () {
        fetch('/insert_email', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email: 'maitreyamoharil@gmail.com' }) // Use the hardcoded email
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                customAlert('Email inserted successfully!');
            } else {
                customAlert('Failed to insert email');
            }
        })
        .catch(error => console.error('Error:', error));
    });
});

function loadEmails() {
    fetch('/get_emails')
        .then(response => response.json())
        .then(data => {
            emailDropdown.innerHTML = ''; // Clear existing items
            data.emails.forEach(email => {
                const li = document.createElement('li');
                li.textContent = email;
                li.addEventListener('click', function () {
                    emailInput.value = email;
                    emailDropdown.style.display = 'none'; // Hide dropdown after selection
                    emailDisplay.textContent = email; // Update the display text
                });
                emailDropdown.appendChild(li);
            });
        });
}

function formatToTimestamp(dateString) {
    if (!dateString) {
        console.warn("Invalid or undefined date:", dateString);
        return 'N/A';
    }

    const date = new Date(dateString);
    return isNaN(date.getTime()) ? 'N/A' : date.toISOString().slice(0, 19).replace('T', ' ');
}

document.addEventListener('DOMContentLoaded', function () {
    const emailInput = document.getElementById('emailInput');
    const emailDisplay = document.querySelector('.email-display');

    // Initially, show the email input field and clear its content
    emailInput.style.display = 'block';
    emailDisplay.style.display = 'none';
    emailInput.value = ''; // Clear any pre-filled value

    // Save the email when it loses focus
    emailInput.addEventListener('blur', function () {
        // Update the email display
        emailDisplay.textContent = emailInput.value;

        // Send the email to the backend for insertion
        fetch('/insert_email', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email: emailInput.value })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                customAlert('Email inserted successfully!');
                // Re-fetch and update dropdown
                loadEmails();
            } else {
                customAlert('Failed to insert email');
            }
        });
    });

    // Toggle dropdown menu on caret click
    dropdownToggle.addEventListener('click', function () {
        emailDropdown.style.display = emailDropdown.style.display === 'none' ? 'block' : 'none';
    });

    // Load emails from the database
    function loadEmails() {
        fetch('/get_emails')
            .then(response => response.json())
            .then(data => {
                emailDropdown.innerHTML = ''; // Clear existing items
                data.emails.forEach(email => {
                    const li = document.createElement('li');
                    li.textContent = email;
                    li.addEventListener('click', function () {
                        // Update the email input box when an email is selected
                        emailInput.value = email;
                        emailDropdown.style.display = 'none'; // Hide dropdown after selection
                        emailDisplay.textContent = email; // Update the display text
                    });
                    emailDropdown.appendChild(li);
                });
            });
    }

    loadEmails(); // Load emails when the page is ready
});

document.addEventListener("DOMContentLoaded", function () {
    document.querySelector(".watchlist-table").addEventListener("click", function (event) {
        if (event.target.classList.contains("ticker-button")) {
            const ticker = event.target.dataset.ticker;
            window.location.href = `/ticker/${ticker}`;
        }
    });
});
