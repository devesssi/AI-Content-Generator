import os
from dotenv import load_dotenv
import streamlit as st
from datetime import datetime, timedelta
import json
import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading
from typing import List, Dict
from serpapi import GoogleSearch
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle

# Load environment variables
load_dotenv()

# Check for required environment variables
required_env_vars = ["OPENROUTER_API_KEY", "SITE_URL", "SITE_NAME", "SERPAPI_KEY"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}. Please check your .env file.")

# Google Calendar API setup
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'primary'  # Use primary calendar

def get_google_calendar_service():
    """Get or create Google Calendar service"""
    try:
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    st.error("credentials.json file not found. Please make sure it's in the same directory as app.py")
                    return None
                
                # Force the authentication flow
                if os.path.exists('token.pickle'):
                    os.remove('token.pickle')
                
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
                
                # Save the credentials
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
        
        service = build('calendar', 'v3', credentials=creds)
        # Test the service by making a simple API call
        service.calendarList().list().execute()
        return service
    except Exception as e:
        st.error(f"Error setting up Google Calendar service: {str(e)}")
        if os.path.exists('token.pickle'):
            os.remove('token.pickle')  # Remove invalid token
        return None

def create_calendar_event(service, title, description, start_date):
    """Create a Google Calendar event"""
    if not service:
        return None
        
    event = {
        'summary': title,
        'description': description,
        'start': {
            'dateTime': start_date.isoformat(),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': (start_date + timedelta(hours=1)).isoformat(),
            'timeZone': 'UTC',
        },
    }
    
    try:
        event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        return event.get('htmlLink')
    except Exception as e:
        st.error(f"Error creating calendar event: {str(e)}")
        return None

def create_session():
    """Create a requests session with retry logic"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def search_web(query: str, search_type: str = "general") -> List[Dict]:
    """Search the web using SerpAPI"""
    try:
        params = {
            "api_key": os.getenv("SERPAPI_KEY"),
            "engine": "google",
            "q": query,
            "num": 5
        }
        
        if search_type == "scholar":
            params["engine"] = "google_scholar"
        elif search_type == "videos":
            params["engine"] = "youtube"
        
        search = GoogleSearch(params)
        results = search.get_dict()
        
        if search_type == "scholar":
            return results.get("organic_results", [])
        elif search_type == "videos":
            return results.get("video_results", [])
        else:
            return results.get("organic_results", [])
            
    except Exception as e:
        st.error(f"Error in web search: {str(e)}")
        return []

def search_pixabay(query: str, count: int = 3) -> List[Dict]:
    """Search for images on Pixabay"""
    api_url = "https://pixabay.com/api/"
    
    params = {
        "key": "36897997-32ed5c1b2cd9b2ad2546d8d8e",  # Free public API key
        "q": query,
        "per_page": count,
        "image_type": "photo",
        "orientation": "horizontal"
    }
    
    try:
        session = create_session()
        response = session.get(
            api_url,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        return result.get('hits', [])
    except Exception as e:
        print(f"Error searching Pixabay: {str(e)}")
        return []
    finally:
        if 'session' in locals():
            session.close()

def generate_content(prompt: str, temperature: float = 0.7) -> str:
    """Generate content using OpenRouter API with Mistral model"""
    api_key = os.getenv("OPENROUTER_API_KEY")
    site_url = os.getenv("SITE_URL")
    site_name = os.getenv("SITE_NAME")
    
    api_url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": site_url,
        "X-Title": site_name
    }
    
    data = {
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": temperature,
        "max_tokens": 2048
    }
    
    try:
        session = create_session()
        response = session.post(
            api_url,
            headers=headers,
            json=data,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
        elif 'response' in result:
            return result['response']
        elif 'text' in result:
            return result['text']
        elif 'content' in result:
            return result['content']
        else:
            raise Exception(f"Unexpected API response format: {json.dumps(result)}")
            
    except requests.exceptions.ConnectionError:
        raise Exception("Network connection error. Please check your internet connection and try again.")
    except requests.exceptions.Timeout:
        raise Exception("Request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error making request: {str(e)}")
    except Exception as e:
        raise Exception(f"Error generating content: {str(e)}")
    finally:
        if 'session' in locals():
            session.close()

def generate_resources_for_topic(topic: str) -> Dict:
    """Generate real resources for a topic"""
    resources = {
        "research": [],
        "videos": [],
        "tools": [],
        "stats": []
    }
    
    # Search for research papers and articles
    research_results = search_web(f"{topic} research papers articles", "scholar")
    for result in research_results:
        resources["research"].append({
            "title": result.get("title", ""),
            "link": result.get("link", ""),
            "snippet": result.get("snippet", "")
        })
    
    # Search for videos
    video_results = search_web(f"{topic} tutorial guide", "videos")
    for result in video_results:
        resources["videos"].append({
            "title": result.get("title", ""),
            "link": result.get("link", ""),
            "thumbnail": result.get("thumbnail", "")
        })
    
    # Search for tools and software
    tool_results = search_web(f"{topic} tools software applications")
    for result in tool_results:
        resources["tools"].append({
            "name": result.get("title", ""),
            "link": result.get("link", ""),
            "description": result.get("snippet", "")
        })
    
    # Search for statistics
    stats_results = search_web(f"{topic} statistics data facts")
    for result in stats_results:
        resources["stats"].append({
            "title": result.get("title", ""),
            "link": result.get("link", ""),
            "snippet": result.get("snippet", "")
        })
    
    return resources

def create_content_calendar(industry: str, target_audience: str, content_goals: str) -> dict:
    """Create a content calendar using the API"""
    try:
        start_time = datetime.now()
        
        # Step 1: Research trends
        research_prompt = f"""Research current trends in the {industry} industry for {target_audience}.
Focus on:
1. Top content formats (video, blog, etc.)
2. Trending topics and hashtags
3. Upcoming events in the next 2 weeks
4. 5-7 potential content topics that align with: {content_goals}

Provide a concise summary (max 500 words)."""
        
        trends = generate_content(research_prompt)
        time.sleep(1)  # Rate limiting
        
        # Step 2: Create strategy
        strategy_prompt = f"""Based on this research: {trends}

Create a simple 7-day content calendar for {target_audience}.
Include:
1. Mix of content types (educational, promotional, etc.)
2. One main topic per day
3. Brief rationale for each day

Format as Day 1: [Topic] - [Type] - [Brief rationale]"""
        
        strategy = generate_content(strategy_prompt)
        time.sleep(1)  # Rate limiting
        
        # Step 3: Create content briefs
        brief_prompt = f"""Based on this calendar: {strategy}

Create brief content outlines for each day.
For each day include:
1. Headline
2. Brief hook
3. 3-5 key points
4. Call-to-action

Keep each day's brief concise and focused."""
        
        briefs = generate_content(brief_prompt)
        time.sleep(1)  # Rate limiting
        
        # Extract topics from strategy
        topics = []
        for line in strategy.split('\n'):
            if line.startswith('Day'):
                topic = line.split(':')[1].split('-')[0].strip()
                topics.append(topic)
        
        # Generate real resources for each topic
        resources = {}
        for topic in topics:
            resources[topic] = generate_resources_for_topic(topic)
            time.sleep(2)  # Rate limiting for SerpAPI
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return {
            'trends': trends,
            'strategy': strategy,
            'briefs': briefs,
            'resources': resources,
            'execution_time': execution_time
        }
        
    except Exception as e:
        return {'error': str(e)}

def save_content_calendar(industry: str, target_audience: str, content_goals: str, result: dict):
    """Save content calendar to a JSON file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"content_calendar_{timestamp}.json"
    
    data = {
        "industry": industry,
        "target_audience": target_audience,
        "content_goals": content_goals,
        "timestamp": timestamp,
        "content_calendar": result
    }
    
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    
    return filename

def main():
    st.set_page_config(page_title="7-Day Content Calendar Creator", layout="wide")
    
    # Initialize session state
    if 'calendar_data' not in st.session_state:
        st.session_state.calendar_data = None
    
    st.title("📅 AI Content Calendar Creator")
    st.subheader("Powered by OpenRouter & Mistral")
    
    st.warning("⚠️ Token Usage Management: Please keep inputs brief to avoid rate limits.")
    
    # Input form with character counters
    with st.form("content_calendar_form"):
        industry = st.text_input("Industry/Niche (max 100 chars)", placeholder="e.g., Fitness, SaaS, Digital Marketing")
        st.caption(f"Characters: {len(industry)}/100")
        
        target_audience = st.text_area("Target Audience (max 200 chars)", placeholder="Key demographics and interests...", height=80)
        st.caption(f"Characters: {len(target_audience)}/200")
        
        content_goals = st.text_area("Content Goals (max 200 chars)", placeholder="e.g., Increase brand awareness...", height=80)
        st.caption(f"Characters: {len(content_goals)}/200")
        
        # Add Google Calendar integration option
        add_to_calendar = st.checkbox("Add to Google Calendar", help="Create events in your Google Calendar for each content piece")
        
        submit_button = st.form_submit_button("Generate 7-Day Content Calendar")
    
    if submit_button:
        if not industry or not target_audience or not content_goals:
            st.error("Please fill out all fields")
            return
        
        progress_container = st.empty()
        progress_bar = st.progress(0)
        status_container = st.empty()
        timer_container = st.empty()
        
        status_container.info("Starting content calendar creation...")
        start_time = datetime.now()
        
        # Timer update thread
        def update_timer():
            while True:
                elapsed = (datetime.now() - start_time).total_seconds()
                timer_container.text(f"⏱️ Time elapsed: {elapsed:.1f}s")
                time.sleep(0.5)
        
        timer_thread = threading.Thread(target=update_timer)
        timer_thread.daemon = True
        timer_thread.start()
        
        result = create_content_calendar(industry, target_audience, content_goals)
        
        if 'error' not in result:
            filename = save_content_calendar(industry, target_audience, content_goals, result)
            
            progress_bar.progress(100)
            status_container.success("Content Calendar Created!")
            timer_container.text(f"⏱️ Total time: {result['execution_time']:.2f}s")
            
            # Store the result in session state
            st.session_state.calendar_data = result
            
            tab1, tab2, tab3, tab4 = st.tabs(["Trends", "Strategy", "Content Briefs", "Resources"])
            
            with tab1:
                st.subheader("Research & Trends")
                st.write(result['trends'])
            
            with tab2:
                st.subheader("7-Day Content Strategy")
                st.write(result['strategy'])
                
                # Add Google Calendar integration
                if add_to_calendar:
                    st.markdown("### 📅 Add to Google Calendar")
                    if st.button("Create Calendar Events", key="calendar_button"):
                        try:
                            # Check if credentials.json exists
                            if not os.path.exists('credentials.json'):
                                st.error("credentials.json file not found. Please make sure it's in the same directory as app.py")
                                return
                            
                            # Force authentication by removing existing token
                            if os.path.exists('token.pickle'):
                                os.remove('token.pickle')
                                
                            service = get_google_calendar_service()
                            if not service:
                                st.error("Failed to initialize Google Calendar service. Please try again.")
                                return
                                
                            start_date = datetime.now()
                            calendar_links = []
                            success_count = 0
                            
                            for line in result['strategy'].split('\n'):
                                if line.startswith('Day'):
                                    try:
                                        day_num = int(line.split(':')[0].split()[1])
                                        topic = line.split(':')[1].split('-')[0].strip()
                                        content_type = line.split('-')[1].strip() if len(line.split('-')) > 1 else "Content"
                                        rationale = line.split('-')[2].strip() if len(line.split('-')) > 2 else ""
                                        
                                        event_date = start_date + timedelta(days=day_num-1)
                                        event_title = f"{topic} - {content_type}"
                                        event_description = f"Content Type: {content_type}\nRationale: {rationale}"
                                        
                                        event_link = create_calendar_event(service, event_title, event_description, event_date)
                                        if event_link:
                                            calendar_links.append(f"Day {day_num}: [{event_title}]({event_link})")
                                            success_count += 1
                                    except Exception as e:
                                        st.warning(f"Error processing day {line}: {str(e)}")
                                        continue
                            
                            if success_count > 0:
                                st.success(f"✅ Successfully created {success_count} calendar events!")
                                st.markdown("### Created Events:")
                                for link in calendar_links:
                                    st.markdown(link)
                            else:
                                st.error("Failed to create any calendar events. Please check your Google Calendar permissions.")
                                
                        except Exception as e:
                            st.error(f"Error creating calendar events: {str(e)}")
                            if os.path.exists('token.pickle'):
                                os.remove('token.pickle')  # Remove invalid token
            
            with tab3:
                st.subheader("Content Briefs")
                st.write(result['briefs'])
            
            with tab4:
                st.subheader("Additional Resources")
                
                # Extract topics from the strategy
                topics = []
                for line in result['strategy'].split('\n'):
                    if line.startswith('Day'):
                        try:
                            topic = line.split(':')[1].split('-')[0].strip()
                            topics.append(topic)
                        except:
                            continue
                
                # Display resources for each topic
                for topic in topics:
                    st.markdown(f"### 📚 Resources for: {topic}")
                    
                    # Create tabs for different resource types
                    resource_tabs = st.tabs([
                        "Research & Articles",
                        "Blogs & Guides",
                        "Videos & Tutorials",
                        "Tools & Software",
                        "Statistics & Data",
                        "Images & Visuals"
                    ])
                    
                    with resource_tabs[0]:
                        st.markdown("#### Academic Research & Articles")
                        research_results = search_web(f"{topic} research papers articles", "scholar")
                        if research_results:
                            for result in research_results[:5]:
                                st.markdown(f"- [{result.get('title', '')}]({result.get('link', '')})")
                                st.caption(result.get('snippet', ''))
                        else:
                            st.info("No research papers found for this topic.")
                    
                    with resource_tabs[1]:
                        st.markdown("#### Blogs & Guides")
                        blog_results = search_web(f"{topic} blog guide tutorial how-to")
                        if blog_results:
                            for result in blog_results[:5]:
                                st.markdown(f"- [{result.get('title', '')}]({result.get('link', '')})")
                                st.caption(result.get('snippet', ''))
                        else:
                            st.info("No blogs or guides found for this topic.")
                    
                    with resource_tabs[2]:
                        st.markdown("#### Videos & Tutorials")
                        video_results = search_web(f"{topic} tutorial guide video", "videos")
                        if video_results:
                            for result in video_results[:5]:
                                st.markdown(f"- [{result.get('title', '')}]({result.get('link', '')})")
                                if result.get('thumbnail'):
                                    st.image(result['thumbnail'], width=200)
                        else:
                            st.info("No videos found for this topic.")
                    
                    with resource_tabs[3]:
                        st.markdown("#### Tools & Software")
                        tool_results = search_web(f"{topic} tools software applications")
                        if tool_results:
                            for result in tool_results[:5]:
                                st.markdown(f"- [{result.get('title', '')}]({result.get('link', '')})")
                                st.caption(result.get('snippet', ''))
                        else:
                            st.info("No tools found for this topic.")
                    
                    with resource_tabs[4]:
                        st.markdown("#### Statistics & Data")
                        stats_results = search_web(f"{topic} statistics data facts trends")
                        if stats_results:
                            for result in stats_results[:5]:
                                st.markdown(f"- [{result.get('title', '')}]({result.get('link', '')})")
                                st.caption(result.get('snippet', ''))
                        else:
                            st.info("No statistics found for this topic.")
                    
                    with resource_tabs[5]:
                        st.markdown("#### Related Images")
                        try:
                            image_results = search_pixabay(topic, count=6)
                            if image_results:
                                cols = st.columns(3)
                                for idx, image in enumerate(image_results):
                                    with cols[idx % 3]:
                                        st.image(image['previewURL'], caption=image['tags'], use_column_width=True)
                                        st.markdown(f"[Source]({image['pageURL']})")
                            else:
                                st.info(f"No images found for {topic}")
                        except Exception as e:
                            st.error(f"Error fetching images for {topic}: {str(e)}")
                    
                    st.markdown("---")
            
            with open(filename, "r") as f:
                st.download_button(
                    label="Download Content Calendar (JSON)",
                    data=f,
                    file_name=filename,
                    mime="application/json"
                )
        else:
            progress_bar.progress(100)
            status_container.error(f"Error: {result['error']}")
            timer_container.empty()

if __name__ == "__main__":
    main() 