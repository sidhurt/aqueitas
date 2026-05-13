import sys
import json
import urllib.request
import argparse

def main():
    parser = argparse.ArgumentParser(description="Aqueitas RAG CLI")
    parser.add_argument("query", type=str, help="Natural language query to search the vault.")
    parser.add_argument("--limit", type=int, default=5, help="Maximum number of logs to retrieve.")
    args = parser.parse_args()

    payload = {
        "query": args.query,
        "limit": args.limit
    }
    
    url = "http://127.0.0.1:8000/query"
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

    # ANSI Escape Codes for strictly formatted, high-status output
    BLUE = "\033[94m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    CYAN = "\033[96m"

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.getcode() == 200:
                res_data = json.loads(response.read().decode('utf-8'))
                
                print(f"\n{BOLD}{CYAN}=== AQUEITAS INTELLIGENCE RETRIEVAL ==={RESET}\n")
                
                print(f"{BOLD}{BLUE}[ANSWER]{RESET}")
                print(f"{res_data['answer']}\n")
                
                print(f"{BOLD}{YELLOW}[SOURCES]{RESET}")
                if not res_data['sources']:
                    print("  No historical logs matched this query.")
                else:
                    for idx, src in enumerate(res_data['sources'], 1):
                        print(f"  {idx}. {BOLD}{src['project_name']}{RESET} (Log ID: {src['log_id']})")
                print("\n" + "="*39 + "\n")
            else:
                print(f"{RED}Error: Server returned {response.getcode()}{RESET}")
    except urllib.error.URLError as e:
        print(f"{RED}Error connecting to Aqueitas Brain: {e.reason}{RESET}")
    except Exception as e:
        print(f"{RED}Unexpected error: {e}{RESET}")

if __name__ == "__main__":
    main()
