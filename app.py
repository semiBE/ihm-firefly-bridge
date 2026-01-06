from flask import Flask, request, jsonify
import requests
import sys
import os
from requests.auth import HTTPBasicAuth
from urllib.parse import urlencode
import logging
import json
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

app = Flask(__name__)

# Configure logging for verbose Docker output
logging.basicConfig(level=logging.INFO,stream=sys.stdout)
logger = logging.getLogger(__name__)
IHM_HOST = os.environ.get("IHM_HOST")  # Docker service name
IHM_PROJECT_SLUG = os.environ.get("IHM_PROJECT_SLUG")
IHM_PROJECT_PASSWORD = os.environ.get("IHM_PROJECT_PASSWORD")
IHM_API_URL = f"{IHM_HOST}/api/projects/{IHM_PROJECT_SLUG}/bills"

@app.route("/firefly-webhook", methods=["POST"])

def firefly_webhook():
    logger.info("📥 Received POST to /firefly-webhook")
    #logger.debug(f"🔧 Raw webhook payload:\n{json.dumps(data, indent=2)}")

    try:
        try:
            data = request.get_json(force=True)
            logger.info("✅ JSON successfully parsed")
            #logger.info(f"🔧 Raw webhook payload:\n{json.dumps(data, indent=2)}")
        except Exception as json_error:
            logger.info("❌ Failed to parse JSON", exc_info=True)
            raw_data = request.data.decode('utf-8', errors='replace')
            logger.info(f"📦 Raw body was:\n{raw_data}")
            return jsonify({"error": "Invalid JSON", "details": str(json_error)}), 400

        # Validate structure
        if 'content' not in data or 'transactions' not in data['content']:
            logger.info("⚠️ Missing expected 'content.transactions' structure")
            return jsonify({"error": "Invalid structure"}), 400

        transaction = data['content']['transactions'][0]

        description = transaction.get('description', 'No description')
        amount = abs(float(transaction.get('amount', 0)))

        source_name = transaction.get("source_name", "").lower()

        # ✅ Only allow transactions from Sodexo
        if "sodexo" not in source_name:
            logger.info("Transaction skipped. Not a Sodexo transaction")
            return jsonify({"status": "skipped", "reason": "Not a Sodexo transaction"}), 200

        if "matteo" in source_name:
            payer = 5
        elif "giulia" in source_name:
            payer = 6
        else:
            payer = "Unknown"

        ihm_payload = {
            "what": description,
            "amount": amount,
            "payer": payer,
            "payed_for": [5, 6],
        }

        #logger.info(f"👥 Determined payer: {payer}, paid_for: ['Matteo', 'Giulia']")

        logger.info(f"🚀 Sending payload to IHM:\n{json.dumps(ihm_payload, indent=2)}")
        form_data = []

        for key, value in ihm_payload.items():
            if isinstance(value, list):
               form_data.extend([(key, v) for v in value])
            else:
               form_data.append((key, value))

        response = requests.post(
            IHM_API_URL,
            data=form_data,
            auth=HTTPBasicAuth(IHM_PROJECT_SLUG, IHM_PROJECT_PASSWORD),
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        json_response = jsonify({"status": response.status_code, "ihm_response": response.json()})
        logger.info(f"{json_response}")
        return jsonify({"status": response.status_code, "ihm_response": response.json()})

    except Exception as e:
        logger.info("❌ Error while processing webhook", exc_info=True)
        return jsonify({"error": str(e), "raw": data}), 400

if __name__ == "__main__":
    logger.info("🚀 Starting Flask app on 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000,debug=True)
