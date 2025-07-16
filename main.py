
import os
import json
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import google.generativeai as genai
from bs4 import BeautifulSoup
import re
import argparse
from urllib.parse import urlparse, urljoin

@dataclass
class RedditPost:
    """Data class for Reddit posts and comments"""
    id: str
    title: str
    content: str
    subreddit: str
    score: int
    created_utc: str
    post_type: str 
    url: str

@dataclass
class UserProfile:
    """Data class for user profile information"""
    username: str
    karma: Dict[str, int]  # post_karma, comment_karma, total_karma
    bio: str
    reddit_age: str
    account_created: str
    active_in: List[str]  # Most active subreddits
    social_links: List[str]
    total_posts: int
    total_comments: int
    avg_score: float
    most_active_subreddits: Dict[str, int]
    posting_frequency: str
    verified: bool
    premium: bool
    profile_img: str
    banner_img: str

@dataclass
class UserPersona:
    """Data class for user persona (privacy-focused)"""
    name: str
    profile: UserProfile
    # Basic Demographics (inferred, not personal)
    age_range: str  # e.g., "25-35", "18-25", "35-45"
    occupation_category: str  # e.g., "Technology", "Creative", "Healthcare"
    status: str  # e.g., "Student", "Professional", "Retired"
    location_type: str  # e.g., "Urban", "Suburban", "Rural"
    
    # Classification
    tier: str  # Early Adopter, Mainstream, Late Adopter
    archetype: str  # The Creator, The Explorer, etc.
    
    # Personality Traits (4 key traits)
    personality_traits: List[str]
    
    # Motivations (1-10 scale)
    motivations: Dict[str, int]
    
    # Personality Scores (visual bars)
    personality_scores: Dict[str, float]
    
    # Behavior patterns
    behavior_habits: List[str]
    frustrations: List[str]
    goals_needs: List[str]
    
    # Representative quote
    quote: str
    
    # Supporting evidence
    citations: Dict[str, List[str]]

class RedditScraper:
    """Scrapes Reddit user profiles and extracts posts/comments"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def extract_username(self, url: str) -> str:
        """Extract username from Reddit URL"""
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        
        if 'user' in path_parts:
            user_index = path_parts.index('user')
            if user_index + 1 < len(path_parts):
                return path_parts[user_index + 1]
        
        raise ValueError(f"Could not extract username from URL: {url}")
    
    def get_user_profile(self, username: str) -> UserProfile:
        """Scrape detailed user profile information"""
        profile_data = {
            'username': username,
            'karma': {'post_karma': 0, 'comment_karma': 0, 'total_karma': 0},
            'bio': '',
            'reddit_age': '',
            'account_created': '',
            'active_in': [],
            'social_links': [],
            'total_posts': 0,
            'total_comments': 0,
            'avg_score': 0.0,
            'most_active_subreddits': {},
            'posting_frequency': '',
            'verified': False,
            'premium': False,
            'profile_img': '',
            'banner_img': ''
        }
        
        try:
            # Get user profile from Reddit API
            about_url = f"https://www.reddit.com/user/{username}/about/.json"
            response = self.session.get(about_url)
            response.raise_for_status()
            
            about_data = response.json()
            user_data = about_data.get('data', {})
            
            # Extract basic profile info
            profile_data['karma'] = {
                'post_karma': user_data.get('link_karma', 0),
                'comment_karma': user_data.get('comment_karma', 0),
                'total_karma': user_data.get('total_karma', 0)
            }
            
            # Calculate Reddit age
            created_utc = user_data.get('created_utc', 0)
            if created_utc:
                created_date = datetime.fromtimestamp(created_utc)
                profile_data['account_created'] = created_date.isoformat()
                age_delta = datetime.now() - created_date
                years = age_delta.days // 365
                months = (age_delta.days % 365) // 30
                if years > 0:
                    profile_data['reddit_age'] = f"{years} year{'s' if years > 1 else ''}, {months} month{'s' if months > 1 else ''}"
                else:
                    profile_data['reddit_age'] = f"{months} month{'s' if months > 1 else ''}"
            
            # Extract profile details
            profile_data['verified'] = user_data.get('verified', False)
            profile_data['premium'] = user_data.get('is_gold', False)
            profile_data['profile_img'] = user_data.get('icon_img', '').replace('&', '&')
            profile_data['banner_img'] = user_data.get('banner_img', '')
            
            # Extract bio and social links from subreddit data
            subreddit_data = user_data.get('subreddit', {})
            if subreddit_data:
                profile_data['bio'] = subreddit_data.get('public_description', '')
                
                # Extract social links from description and public_description
                description_text = subreddit_data.get('description', '')
                public_desc = subreddit_data.get('public_description', '')
                combined_text = f"{description_text} {public_desc}"
                
                social_links = self._extract_social_links(combined_text)
                profile_data['social_links'] = social_links
            
            # Also try to get social links from the user's profile page HTML
            try:
                profile_html_url = f"https://www.reddit.com/user/{username}/"
                html_response = self.session.get(profile_html_url)
                if html_response.status_code == 200:
                    soup = BeautifulSoup(html_response.text, 'html.parser')
                    
                    # Look for social links in various places
                    social_links_html = self._extract_social_links_from_html(soup)
                    profile_data['social_links'].extend(social_links_html)
                    
                    # Remove duplicates
                    profile_data['social_links'] = list(set(profile_data['social_links']))
                    
            except Exception as e:
                print(f"Could not fetch HTML profile: {e}")
            
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            print(f"Error fetching profile data: {e}")
        
        return UserProfile(**profile_data)
    
    def _extract_social_links_from_html(self, soup: BeautifulSoup) -> List[str]:
        """Extract social links from HTML content"""
        links = []
        
        # Look for links in various HTML elements
        all_links = soup.find_all('a', href=True)
        
        social_domains = [
            'twitter.com', 'x.com', 'instagram.com', 'facebook.com', 
            'linkedin.com', 'youtube.com', 'twitch.tv', 'github.com', 
            'discord.gg', 'tiktok.com', 'snapchat.com', 'telegram.me',
            't.me', 'medium.com', 'dev.to', 'stackoverflow.com'
        ]
        
        for link in all_links:
            href = link.get('href', '')
            if any(domain in href for domain in social_domains):
                if href.startswith('http'):
                    links.append(href)
        
        return links
    
    def _extract_social_links(self, text: str) -> List[str]:
        """Extract social media links from text"""
        social_patterns = [
            r'https?://(?:www\.)?(?:twitter\.com|x\.com)/\w+',
            r'https?://(?:www\.)?instagram\.com/\w+',
            r'https?://(?:www\.)?facebook\.com/\w+',
            r'https?://(?:www\.)?linkedin\.com/in/[\w-]+',
            r'https?://(?:www\.)?youtube\.com/(?:channel/|user/|c/)?[\w-]+',
            r'https?://(?:www\.)?twitch\.tv/\w+',
            r'https?://(?:www\.)?github\.com/\w+',
            r'https?://(?:www\.)?discord\.gg/\w+',
            r'https?://(?:www\.)?tiktok.com/@\w+',
            r'https?://(?:www\.)?snapchat\.com/add/\w+',
            r'https?://(?:t\.me|telegram\.me)/\w+',
            r'https?://(?:www\.)?medium\.com/@\w+',
            r'https?://(?:www\.)?dev\.to/\w+',
            r'https?://(?:www\.)?stackoverflow\.com/users/\d+/[\w-]+'
        ]
        
        links = []
        for pattern in social_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            links.extend(matches)
        
        return links
    
    def get_user_data(self, username: str, limit: int = 100) -> List[RedditPost]:
        """
        Scrape user's posts and comments using Reddit's JSON API
        """
        posts = []
        
        # Get user's submitted posts
        try:
            submitted_url = f"https://www.reddit.com/user/{username}/submitted/.json?limit={limit}"
            response = self.session.get(submitted_url)
            response.raise_for_status()
            
            submitted_data = response.json()
            
            for post in submitted_data.get('data', {}).get('children', []):
                post_data = post['data']
                posts.append(RedditPost(
                    id=post_data.get('id', ''),
                    title=post_data.get('title', ''),
                    content=post_data.get('selftext', ''),
                    subreddit=post_data.get('subreddit', ''),
                    score=post_data.get('score', 0),
                    created_utc=datetime.fromtimestamp(post_data.get('created_utc', 0)).isoformat(),
                    post_type='post',
                    url=f"https://www.reddit.com{post_data.get('permalink', '')}"
                ))
            
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            print(f"Error fetching submitted posts: {e}")
        
        # Get user's comments
        try:
            comments_url = f"https://www.reddit.com/user/{username}/comments/.json?limit={limit}"
            response = self.session.get(comments_url)
            response.raise_for_status()
            
            comments_data = response.json()
            
            for comment in comments_data.get('data', {}).get('children', []):
                comment_data = comment['data']
                posts.append(RedditPost(
                    id=comment_data.get('id', ''),
                    title='',  # Comments don't have titles
                    content=comment_data.get('body', ''),
                    subreddit=comment_data.get('subreddit', ''),
                    score=comment_data.get('score', 0),
                    created_utc=datetime.fromtimestamp(comment_data.get('created_utc', 0)).isoformat(),
                    post_type='comment',
                    url=f"https://www.reddit.com{comment_data.get('permalink', '')}"
                ))
            
        except Exception as e:
            print(f"Error fetching comments: {e}")
        
        return posts
    
    def analyze_posting_patterns(self, posts: List[RedditPost], profile: UserProfile) -> UserProfile:
        """Analyze posting patterns and update profile"""
        if not posts:
            return profile
        
        # Count posts and comments
        post_count = sum(1 for p in posts if p.post_type == 'post')
        comment_count = sum(1 for p in posts if p.post_type == 'comment')
        
        profile.total_posts = post_count
        profile.total_comments = comment_count
        
        # Calculate average score
        total_score = sum(p.score for p in posts)
        profile.avg_score = total_score / len(posts) if posts else 0
        
        # Find most active subreddits
        subreddit_counts = {}
        for post in posts:
            subreddit = post.subreddit
            subreddit_counts[subreddit] = subreddit_counts.get(subreddit, 0) + 1
        
        # Sort by activity and get top 10
        profile.most_active_subreddits = dict(sorted(subreddit_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        profile.active_in = list(profile.most_active_subreddits.keys())[:10]  # Get top 10 active communities
        
        # Calculate posting frequency
        if posts:
            dates = [datetime.fromisoformat(p.created_utc.replace('Z', '+00:00')) for p in posts]
            if len(dates) > 1:
                date_range = max(dates) - min(dates)
                if date_range.days > 0:
                    posts_per_day = len(posts) / date_range.days
                    if posts_per_day >= 1:
                        profile.posting_frequency = f"{posts_per_day:.1f} posts/day"
                    else:
                        profile.posting_frequency = f"{posts_per_day * 7:.1f} posts/week"
                else:
                    profile.posting_frequency = "Very active (multiple posts per day)"
            else:
                profile.posting_frequency = "Limited data"
        
        return profile

class PersonaGenerator:
    """Generates user personas using Google's Gemini API"""
    
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        # List available models for debugging
        try:
            models = genai.list_models()
            print("Available models:")
            for model in models:
                print(f"- {model.name}")
        except Exception as e:
            print(f"Error listing models: {e}")
        # Initialize with a default model (will try fallbacks in generate_persona)
        self.model = None
    
    def generate_persona(self, posts: List[RedditPost], profile: UserProfile) -> UserPersona:
        """Generate a user persona from Reddit posts and profile using Gemini (privacy-focused)"""
        
        posts_text = self._prepare_posts_for_analysis(posts)
        profile_text = self._prepare_profile_for_analysis(profile)
        
        prompt = f"""
        Analyze the following Reddit user profile and posts/comments to create a detailed user persona similar to the professional user personas used in UX design.
        
        IMPORTANT: DO NOT extract or infer personal identifying information such as:
        - Real names, ages, specific locations, addresses
        - Specific occupation details that could identify the person
        - Relationship status or family information
        - Any other personally identifiable information
        
        Instead, infer GENERAL categories and ranges that are useful for design purposes.
        
        USER PROFILE INFORMATION:
        {profile_text}
        
        POSTS AND COMMENTS:
        {posts_text}
        
        Based on this comprehensive data, create a detailed user persona that includes:
        
        1. BASIC DEMOGRAPHICS (General categories only):
           - Age range (e.g., "25-35", "18-25", "35-45", "45+")
           - Occupation category (e.g., "Technology", "Creative", "Healthcare", "Student", "Business")
           - Status (e.g., "Student", "Professional", "Freelancer", "Retired")
           - Location type (e.g., "Urban", "Suburban", "Rural")
        
        2. USER CLASSIFICATION:
           - User tier (Early Adopter, Mainstream, Late Adopter based on Reddit behavior)
           - Archetype (The Creator, The Explorer, The Caregiver, The Rebel, The Sage, The Innocent, The Hero, The Magician, The Lover, The Jester, The Everyman, The Ruler)
        
        3. PERSONALITY TRAITS (exactly 4 key traits like Practical, Adaptable, Spontaneous, Active, Analytical, Creative, Helpful, Critical, etc.)
        
        4. MOTIVATIONS (rate 1-10):
           - CONVENIENCE
           - WELLNESS
           - SPEED
           - PREFERENCES
           - COMFORT
           - DIETARY_NEEDS (or relevant motivation based on context)
        
        5. PERSONALITY DIMENSIONS (0.0-1.0 scale):
           - INTROVERT (0.0) vs EXTROVERT (1.0)
           - INTUITION (0.0) vs SENSING (1.0)
           - FEELING (0.0) vs THINKING (1.0)
           - PERCEIVING (0.0) vs JUDGING (1.0)
        
        6. BEHAVIOR & HABITS (3-5 specific behaviors observed from Reddit activity)
        
        7. FRUSTRATIONS (3-5 pain points or complaints expressed in posts)
        
        8. GOALS & NEEDS (3-4 main objectives or desires based on content)
        
        9. A representative quote that captures their Reddit persona and communication style
        
        10. For each major characteristic, provide specific citations (post/comment IDs and brief excerpts)
        
        Consider the user's:
        - Karma levels and community engagement
        - Reddit age and experience level
        - Active subreddits and interests
        - Posting frequency and activity patterns
        - Communication style and tone
        - Types of content they engage with
        - Technical knowledge level
        - Interests and hobbies
        
        Format your response as a JSON object with the following structure:
        {{
            "name": "Generated persona name (not real name)",
            "age_range": "age range",
            "occupation_category": "occupation category",
            "status": "status",
            "location_type": "location type",
            "tier": "user tier",
            "archetype": "user archetype",
            "personality_traits": ["trait1", "trait2", "trait3", "trait4"],
            "motivations": {{
                "CONVENIENCE": 7,
                "WELLNESS": 5,
                "SPEED": 6,
                "PREFERENCES": 8,
                "COMFORT": 7,
                "DIETARY_NEEDS": 6
            }},
            "personality_scores": {{
                "introvert_extrovert": 0.3,
                "intuition_sensing": 0.7,
                "feeling_thinking": 0.4,
                "perceiving_judging": 0.6
            }},
            "behavior_habits": ["habit1", "habit2", "habit3"],
            "frustrations": ["frustration1", "frustration2", "frustration3"],
            "goals_needs": ["goal1", "goal2", "goal3"],
            "quote": "A representative quote from their content or communication style",
            "citations": {{
                "personality_traits": ["post_id: excerpt"],
                "behavior_habits": ["post_id: excerpt"],
                "frustrations": ["post_id: excerpt"],
                "goals_needs": ["post_id: excerpt"]
            }}
        }}
        
        Base all inferences on actual content from the posts and profile data. Focus on behavioral patterns, interests, and communication style rather than personal details.
        """
        
        try:
            # Try multiple models as fallback
            models = ['gemini-1.5-pro', 'gemini-1.5-flash']  # Updated model list
            response = None
            for model_name in models:
                try:
                    self.model = genai.GenerativeModel(model_name)
                    response = self.model.generate_content(prompt)
                    print(f"Successfully used model: {model_name}")
                    break
                except Exception as e:
                    print(f"Model {model_name} failed: {e}")
            
            if response is None:
                raise Exception("All model attempts failed")
            
            # Log raw response for debugging
            print("Raw API response:", response.text)
            
            # Parse the JSON response
            json_start = response.text.find('{')
            json_end = response.text.rfind('}') + 1
            json_str = response.text[json_start:json_end]
            
            persona_data = json.loads(json_str)
            
            return UserPersona(
                name=persona_data.get('name', f"{profile.username} Persona"),
                profile=profile,
                age_range=persona_data.get('age_range', 'Unknown'),
                occupation_category=persona_data.get('occupation_category', 'Unknown'),
                status=persona_data.get('status', 'Unknown'),
                location_type=persona_data.get('location_type', 'Unknown'),
                tier=persona_data.get('tier', 'Unknown'),
                archetype=persona_data.get('archetype', 'Unknown'),
                personality_traits=persona_data.get('personality_traits', []),
                motivations=persona_data.get('motivations', {}),
                personality_scores=persona_data.get('personality_scores', {}),
                behavior_habits=persona_data.get('behavior_habits', []),
                frustrations=persona_data.get('frustrations', []),
                goals_needs=persona_data.get('goals_needs', []),
                quote=persona_data.get('quote', ''),
                citations=persona_data.get('citations', {})
            )
            
        except Exception as e:
            print(f"Error generating persona: {e}")
            return self._create_default_persona(profile)
    
    def _prepare_profile_for_analysis(self, profile: UserProfile) -> str:
        """Prepare profile data for analysis"""
        profile_text = f"""
Username: {profile.username}
Reddit Age: {profile.reddit_age}
Account Created: {profile.account_created}

KARMA:
- Post Karma: {profile.karma.get('post_karma', 0):,}
- Comment Karma: {profile.karma.get('comment_karma', 0):,}
- Total Karma: {profile.karma.get('total_karma', 0):,}

ACTIVITY:
- Total Posts: {profile.total_posts}
- Total Comments: {profile.total_comments}
- Average Score: {profile.avg_score:.1f}
- Posting Frequency: {profile.posting_frequency}

ACTIVE COMMUNITIES:
{chr(10).join(f"- r/{sub}: {count} posts" for sub, count in profile.most_active_subreddits.items())}

BIO: {profile.bio or 'No bio provided'}

SOCIAL LINKS: {', '.join(profile.social_links) if profile.social_links else 'None'}

ACCOUNT STATUS:
- Verified: {profile.verified}
- Premium: {profile.premium}
"""
        return profile_text
    
    def _prepare_posts_for_analysis(self, posts: List[RedditPost]) -> str:
        """Prepare posts for analysis by Gemini"""
        posts_text = ""
        for i, post in enumerate(posts[:50]):  # Limit to first 50 posts to avoid token limits
            posts_text += f"\n--- Post/Comment {i+1} (ID: {post.id}) ---\n"
            posts_text += f"Type: {post.post_type}\n"
            posts_text += f"Subreddit: r/{post.subreddit}\n"
            posts_text += f"Score: {post.score}\n"
            posts_text += f"Date: {post.created_utc}\n"
            if post.title:
                posts_text += f"Title: {post.title}\n"
            posts_text += f"Content: {post.content[:500]}...\n"  # Truncate long content
        
        return posts_text
    
    def _create_default_persona(self, profile: UserProfile) -> UserPersona:
        """Create a default persona when generation fails"""
        return UserPersona(
            name=f"{profile.username} Persona",
            profile=profile,
            age_range="Unknown",
            occupation_category="Unknown",
            status="Unknown",
            location_type="Unknown",
            tier="Unknown",
            archetype="Unknown",
            personality_traits=["Unknown"],
            motivations={},
            personality_scores={},
            behavior_habits=["Unknown"],
            frustrations=["Unknown"],
            goals_needs=["Unknown"],
            quote="No quote available",
            citations={}
        )

class PersonaFormatter:
    """Formats the persona output"""
    
    def format_persona_text(self, persona: UserPersona) -> str:
        """Format persona as human-readable text similar to the image"""
        
        text = f"""
{'='*80}
{persona.name.upper()}
{'='*80}

BASIC INFORMATION:
- Age Range: {persona.age_range}
- Occupation: {persona.occupation_category}
- Status: {persona.status}
- Location Type: {persona.location_type}
- Tier: {persona.tier}
- Archetype: {persona.archetype}

PERSONALITY TRAITS:
{self._format_traits(persona.personality_traits)}

MOTIVATIONS:
{self._format_motivations(persona.motivations)}

PERSONALITY DIMENSIONS:
{self._format_personality_scores(persona.personality_scores)}

BEHAVIOR & HABITS:
{self._format_list(persona.behavior_habits)}

FRUSTRATIONS:
{self._format_list(persona.frustrations)}

GOALS & NEEDS:
{self._format_list(persona.goals_needs)}

REPRESENTATIVE QUOTE:
"{persona.quote}"

{'='*80}
REDDIT PROFILE DATA
{'='*80}

- Username: {persona.profile.username}
- Reddit Age: {persona.profile.reddit_age}
- Account Created: {persona.profile.account_created}
- Post Karma: {persona.profile.karma.get('post_karma', 0):,}
- Comment Karma: {persona.profile.karma.get('comment_karma', 0):,}
- Total Karma: {persona.profile.karma.get('total_karma', 0):,}
- Verified: {'Yes' if persona.profile.verified else 'No'}
- Premium: {'Yes' if persona.profile.premium else 'No'}

ACTIVITY SUMMARY:
- Total Posts: {persona.profile.total_posts}
- Total Comments: {persona.profile.total_comments}
- Average Score: {persona.profile.avg_score:.1f}
- Posting Frequency: {persona.profile.posting_frequency}

ACTIVE COMMUNITIES:
{self._format_subreddits(persona.profile.most_active_subreddits)}

BIO: {persona.profile.bio or 'No bio provided'}

SOCIAL LINKS:
{self._format_list(persona.profile.social_links) if persona.profile.social_links else '- None'}

CITATIONS:
{self._format_citations(persona.citations)}

{'='*80}
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*80}
"""
        return text
    
    def _format_traits(self, traits: List[str]) -> str:
        """Format personality traits as boxes"""
        if not traits:
            return "- None specified"
        
        formatted_traits = []
        for trait in traits:
            formatted_traits.append(f"[{trait}]")
        
        return "  ".join(formatted_traits)
    
    def _format_subreddits(self, subreddits: Dict[str, int]) -> str:
        """Format subreddits with post counts"""
        if not subreddits:
            return "- None"
        return '\n'.join(f"- r/{sub}: {count} posts" for sub, count in subreddits.items())
    
    def _format_list(self, items: List[str]) -> str:
        """Format a list of items with bullet points"""
        if not items:
            return "- None specified"
        return '\n'.join(f"• {item}" for item in items)
    
    def _format_motivations(self, motivations: Dict[str, int]) -> str:
        """Format motivations with visual bars"""
        if not motivations:
            return "- None specified"
        
        formatted = []
        for key, value in motivations.items():
            # Create visual bar (filled and empty blocks)
            filled = '█' * value
            empty = '░' * (10 - value)
            bar = filled + empty
            formatted.append(f"{key:<15} {bar}")
        
        return '\n'.join(formatted)
    
    def _format_personality_scores(self, scores: Dict[str, float]) -> str:
        """Format personality scores with visual sliders"""
        if not scores:
            return "- None specified"
        
        formatted = []
        for key, value in scores.items():
            if 'introvert' in key.lower():
                left, right = 'INTROVERT', 'EXTROVERT'
            elif 'intuition' in key.lower():
                left, right = 'INTUITION', 'SENSING'
            elif 'feeling' in key.lower():
                left, right = 'FEELING', 'THINKING'
            elif 'perceiving' in key.lower():
                left, right = 'PERCEIVING', 'JUDGING'
            else:
                left, right = key.split('_')
            
            # Create visual slider
            position = int(value * 20)
            bar = '░' * position + '█' + '░' * (19 - position)
            formatted.append(f"{left.upper():<12} {bar} {right.upper()}")
        
        return '\n'.join(formatted)
    
    def _format_citations(self, citations: Dict[str, List[str]]) -> str:
        """Format citations with sources"""
        if not citations:
            return "- No citations available"
        
        formatted = []
        for category, sources in citations.items():
            formatted.append(f"\n{category.upper()}:")
            for source in sources:
                formatted.append(f"  - {source}")
        
        return '\n'.join(formatted)
    
    def generate_html_persona(self, persona: UserPersona) -> str:
        """Generate HTML format similar to the image"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{persona.name}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .persona-container {{
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .persona-header {{
            text-align: center;
            border-bottom: 2px solid #333;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .persona-name {{
            font-size: 2.5em;
            font-weight: bold;
            color: #333;
            margin: 0;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .section-title {{
            font-size: 1.3em;
            font-weight: bold;
            color: #444;
            margin-bottom: 15px;
            border-bottom: 1px solid #ddd;
            padding-bottom: 5px;
        }}
        .trait-box {{
            display: inline-block;
            background: #e8f4f8;
            border: 1px solid #bee5eb;
            border-radius: 5px;
            padding: 5px 10px;
            margin: 5px;
            font-weight: bold;
            color: #0c5460;
        }}
        .motivation-bar {{
            margin: 10px 0;
            display: flex;
            align-items: center;
        }}
        .motivation-label {{
            width: 120px;
            font-weight: bold;
        }}
        .bar-container {{
            flex: 1;
            height: 20px;
            background: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
            margin: 0 10px;
        }}
        .bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, #ff6b6b, #ffa500, #32cd32);
            transition: width 0.5s ease;
        }}
        .personality-slider {{
            margin: 15px 0;
            display: flex;
            align-items: center;
        }}
        .slider-label {{
            width: 100px;
            font-size: 0.9em;
            font-weight: bold;
        }}
        .slider-container {{
            flex: 1;
            height: 8px;
            background: #e0e0e0;
            border-radius: 4px;
            position: relative;
            margin: 0 10px;
        }}
        .slider-thumb {{
            position: absolute;
            top: -6px;
            width: 20px;
            height: 20px;
            background: #007bff;
            border-radius: 50%;
            border: 2px solid white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}
        .list-item {{
            margin: 5px 0;
            padding-left: 20px;
            position: relative;
        }}
        .list-item::before {{
            content: "•";
            position: absolute;
            left: 0;
            color: #007bff;
            font-weight: bold;
        }}
        .quote-box {{
            background: #f8f9fa;
            border-left: 4px solid #007bff;
            padding: 20px;
            margin: 20px 0;
            font-style: italic;
            font-size: 1.1em;
        }}
        .profile-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-box {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #007bff;
        }}
        .stat-label {{
            font-size: 0.9em;
            color: #666;
        }}
        .subreddit-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .subreddit-tag {{
            background: #e9ecef;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 0.9em;
            color: #495057;
        }}
    </style>
</head>
<body>
    <div class="persona-container">
        <div class="persona-header">
            <h1 class="persona-name">{persona.name}</h1>
        </div>
        
        <div class="section">
            <h2 class="section-title">Basic Information</h2>
            <p><strong>Age Range:</strong> {persona.age_range}</p>
            <p><strong>Occupation:</strong> {persona.occupation_category}</p>
            <p><strong>Status:</strong> {persona.status}</p>
            <p><strong>Location Type:</strong> {persona.location_type}</p>
            <p><strong>Tier:</strong> {persona.tier}</p>
            <p><strong>Archetype:</strong> {persona.archetype}</p>
        </div>
        
        <div class="section">
            <h2 class="section-title">Personality Traits</h2>
            <div>
                {self._format_traits_html(persona.personality_traits)}
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">Motivations</h2>
            {self._format_motivations_html(persona.motivations)}
        </div>
        
        <div class="section">
            <h2 class="section-title">Personality Dimensions</h2>
            {self._format_personality_scores_html(persona.personality_scores)}
        </div>
        
        <div class="section">
            <h2 class="section-title">Behavior & Habits</h2>
            {self._format_list_html(persona.behavior_habits)}
        </div>
        
        <div class="section">
            <h2 class="section-title">Fruestrations</h2>
            {self._format_list_html(persona.frustrations)}
        </div>
        
        <div class="section">
            <h2 class="section-title">Goals & Needs</h2>
            {self._format_list_html(persona.goals_needs)}
        </div>
        
        <div class="section">
            <h2 class="section-title">Representative Quote</h2>
            <div class="quote-box">
                "{persona.quote}"
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">Reddit Profile</h2>
            <div class="profile-stats">
                <div class="stat-box">
                    <div class="stat-number">{persona.profile.karma.get('total_karma', 0):,}</div>
                    <div class="stat-label">Total Karma</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{persona.profile.total_posts}</div>
                    <div class="stat-label">Total Posts</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{persona.profile.total_comments}</div>
                    <div class="stat-label">Total Comments</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{persona.profile.avg_score:.1f}</div>
                    <div class="stat-label">Average Score</div>
                </div>
            </div>
            
            <p><strong>Username:</strong> {persona.profile.username}</p>
            <p><strong>Reddit Age:</strong> {persona.profile.reddit_age}</p>
            <p><strong>Posting Frequency:</strong> {persona.profile.posting_frequency}</p>
            <p><strong>Verified:</strong> {'Yes' if persona.profile.verified else 'No'}</p>
            <p><strong>Premium:</strong> {'Yes' if persona.profile.premium else 'No'}</p>
            
            <h3>Active Communities</h3>
            <div class="subreddit-list">
                {self._format_subreddits_html(persona.profile.most_active_subreddits)}
            </div>
            
            <h3>Bio</h3>
            <p>{persona.profile.bio or 'No bio provided'}</p>
            
            <h3>Social Links</h3>
            {self._format_social_links_html(persona.profile.social_links)}
        </div>
        
        <div class="section">
            <h2 class="section-title">Citations</h2>
            {self._format_citations_html(persona.citations)}
        </div>
        
        <div style="text-align: center; margin-top: 30px; color: #666; font-size: 0.9em;">
            Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def _format_traits_html(self, traits: List[str]) -> str:
        """Format personality traits as HTML boxes"""
        if not traits:
            return "<p>None specified</p>"
        
        html = ""
        for trait in traits:
            html += f'<span class="trait-box">{trait}</span>'
        
        return html
    
    def _format_motivations_html(self, motivations: Dict[str, int]) -> str:
        """Format motivations with HTML bars"""
        if not motivations:
            return "<p>None specified</p>"
        
        html = ""
        for key, value in motivations.items():
            percentage = (value / 10) * 100
            html += f'''
            <div class="motivation-bar">
                <div class="motivation-label">{key}</div>
                <div class="bar-container">
                    <div class="bar-fill" style="width: {percentage}%"></div>
                </div>
                <div>{value}/10</div>
            </div>
            '''
        
        return html
    
    def _format_personality_scores_html(self, scores: Dict[str, float]) -> str:
        """Format personality scores with HTML sliders"""
        if not scores:
            return "<p>None specified</p>"
        
        html = ""
        for key, value in scores.items():
            if 'introvert' in key.lower():
                left, right = 'INTROVERT', 'EXTROVERT'
            elif 'intuition' in key.lower():
                left, right = 'INTUITION', 'SENSING'
            elif 'feeling' in key.lower():
                left, right = 'FEELING', 'THINKING'
            elif 'perceiving' in key.lower():
                left, right = 'PERCEIVING', 'JUDGING'
            else:
                left, right = key.split('_')
            
            percentage = value * 100
            html += f'''
            <div class="personality-slider">
                <div class="slider-label">{left.upper()}</div>
                <div class="slider-container">
                    <div class="slider-thumb" style="left: {percentage}%"></div>
                </div>
                <div class="slider-label">{right.upper()}</div>
            </div>
            '''
        
        return html
    
    def _format_list_html(self, items: List[str]) -> str:
        """Format a list of items with HTML bullet points"""
        if not items:
            return "<p>None specified</p>"
        
        html = ""
        for item in items:
            html += f'<div class="list-item">{item}</div>'
        
        return html
    
    def _format_subreddits_html(self, subreddits: Dict[str, int]) -> str:
        """Format subreddits as HTML tags"""
        if not subreddits:
            return "<p>None</p>"
        
        html = ""
        for sub, count in subreddits.items():
            html += f'<span class="subreddit-tag">r/{sub} ({count})</span>'
        
        return html
    
    def _format_social_links_html(self, links: List[str]) -> str:
        """Format social links as HTML links"""
        if not links:
            return "<p>None</p>"
        
        html = "<ul>"
        for link in links:
            html += f'<li><a href="{link}" target="_blank">{link}</a></li>'
        html += "</ul>"
        
        return html
    
    def _format_citations_html(self, citations: Dict[str, List[str]]) -> str:
        """Format citations as HTML"""
        if not citations:
            return "<p>No citations available</p>"
        
        html = ""
        for category, sources in citations.items():
            html += f"<h3>{category.replace('_', ' ').title()}</h3><ul>"
            for source in sources:
                html += f"<li>{source}</li>"
            html += "</ul>"
        
        return html

def main():
    """Main function to run the persona generator"""
    parser = argparse.ArgumentParser(description='Generate Reddit user personas')
    parser.add_argument('reddit_url', help='Reddit user profile URL')
    parser.add_argument('--gemini-api-key', help='Google Gemini API key (or set GEMINI_API_KEY env var)')
    parser.add_argument('--limit', type=int, default=100, help='Number of posts/comments to analyze (default: 100)')
    parser.add_argument('--output-format', choices=['text', 'html', 'json'], default='text', help='Output format')
    parser.add_argument('--output-file', help='Output file path (optional, defaults to persona_output.<format>)')
    
    args = parser.parse_args()
    
    # Get API key
    api_key = args.gemini_api_key or os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Error: Please provide a Gemini API key via --gemini-api-key or GEMINI_API_KEY environment variable")
        return
    
    try:
        # Initialize components
        scraper = RedditScraper()
        generator = PersonaGenerator(api_key)
        formatter = PersonaFormatter()
        
        # Extract username from URL
        username = scraper.extract_username(args.reddit_url)
        print(f"Analyzing user: {username}")
        
        # Get user profile
        print("Fetching user profile...")
        profile = scraper.get_user_profile(username)
        
        # Get user posts and comments
        print(f"Fetching {args.limit} posts and comments...")
        posts = scraper.get_user_data(username, args.limit)
        
        # Analyze posting patterns
        print("Analyzing posting patterns...")
        profile = scraper.analyze_posting_patterns(posts, profile)
        
        # Generate persona
        print("Generating persona with AI...")
        persona = generator.generate_persona(posts, profile)
        
        # Format output
        if args.output_format == 'text':
            output = formatter.format_persona_text(persona)
            default_file = f"persona_output.txt"
        elif args.output_format == 'html':
            output = formatter.generate_html_persona(persona)
            default_file = f"persona_output.html"
        elif args.output_format == 'json':
            output = json.dumps(asdict(persona), indent=2, default=str)
            default_file = f"persona_output.json"
        
        # Save output to file
        output_file = args.output_file or default_file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"Persona saved to: {output_file}")
            
    except Exception as e:
        print(f"Error: {e}")
        return

if __name__ == "__main__":
    main()