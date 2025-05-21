import requests
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import json

from app.config import settings

class LinkedInAPI:
    """
    LinkedIn API client for posting content and retrieving analytics
    """
    
    BASE_URL = "https://api.linkedin.com/v2"
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }
    
    def get_profile(self) -> Dict[str, Any]:
        """Get the user's LinkedIn profile"""
        url = f"{self.BASE_URL}/me"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def create_text_post(self, author_id: str, text: str) -> Dict[str, Any]:
        """Create a text-only post on LinkedIn"""
        url = f"{self.BASE_URL}/ugcPosts"
        
        payload = {
            "author": f"urn:li:person:{author_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()
    
    def create_image_post(self, author_id: str, text: str, image_url: str) -> Dict[str, Any]:
        """Create a post with an image on LinkedIn"""
        # First, register the image
        register_url = f"{self.BASE_URL}/assets?action=registerUpload"
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": f"urn:li:person:{author_id}",
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent"
                    }
                ]
            }
        }
        
        register_response = requests.post(register_url, headers=self.headers, json=register_payload)
        register_response.raise_for_status()
        register_data = register_response.json()
        
        # Upload the image
        upload_url = register_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
        asset_id = register_data["value"]["asset"]
        
        # Download the image from the provided URL
        image_response = requests.get(image_url)
        image_response.raise_for_status()
        
        # Upload to LinkedIn
        upload_response = requests.put(
            upload_url, 
            data=image_response.content,
            headers={
                "Authorization": f"Bearer {self.access_token}"
            }
        )
        upload_response.raise_for_status()
        
        # Create the post with the uploaded image
        post_url = f"{self.BASE_URL}/ugcPosts"
        post_payload = {
            "author": f"urn:li:person:{author_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "IMAGE",
                    "media": [
                        {
                            "status": "READY",
                            "description": {
                                "text": "Image"
                            },
                            "media": asset_id,
                            "title": {
                                "text": "Image"
                            }
                        }
                    ]
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        post_response = requests.post(post_url, headers=self.headers, json=post_payload)
        post_response.raise_for_status()
        return post_response.json()
    
    def get_post_analytics(self, post_id: str) -> Dict[str, Any]:
        """Get analytics for a specific post"""
        url = f"{self.BASE_URL}/socialActions/{post_id}"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        
        # Extract analytics data
        analytics = {
            "likes": data.get("likesSummary", {}).get("totalLikes", 0),
            "comments": data.get("commentsSummary", {}).get("totalComments", 0),
            "shares": data.get("sharesSummary", {}).get("totalShares", 0)
        }
        
        return analytics
    
    def get_profile_analytics(self, profile_id: str, timeframe: str = "ONE_MONTH") -> Dict[str, Any]:
        """Get analytics for the user's profile"""
        url = f"{self.BASE_URL}/organizationalEntityShareStatistics?q=organizationalEntity&organizationalEntity=urn:li:person:{profile_id}&timeIntervals.timeGranularityType={timeframe}&timeIntervals.timeRange.start=0"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        
        # Extract analytics data
        analytics = {
            "impressions": 0,
            "clicks": 0,
            "engagement_rate": 0.0,
            "data_points": []
        }
        
        # Process the data
        if "elements" in data:
            for element in data["elements"]:
                stats = element.get("totalShareStatistics", {})
                analytics["impressions"] += stats.get("impressionCount", 0)
                analytics["clicks"] += stats.get("clickCount", 0)
                
                # Calculate engagement rate
                if analytics["impressions"] > 0:
                    engagement = stats.get("likeCount", 0) + stats.get("commentCount", 0) + stats.get("shareCount", 0)
                    analytics["engagement_rate"] = (engagement / analytics["impressions"]) * 100
                
                # Add data point
                timestamp = element.get("timeRange", {}).get("start", 0)
                if timestamp:
                    date = datetime.fromtimestamp(timestamp / 1000)
                    analytics["data_points"].append({
                        "date": date.isoformat(),
                        "impressions": stats.get("impressionCount", 0),
                        "clicks": stats.get("clickCount", 0),
                        "likes": stats.get("likeCount", 0),
                        "comments": stats.get("commentCount", 0),
                        "shares": stats.get("shareCount", 0)
                    })
        
        return analytics

def get_linkedin_auth_url() -> str:
    """Get the LinkedIn OAuth authorization URL"""
    return (
        f"https://www.linkedin.com/oauth/v2/authorization"
        f"?response_type=code"
        f"&client_id={settings.LINKEDIN_CLIENT_ID}"
        f"&redirect_uri={settings.LINKEDIN_REDIRECT_URI}"
        f"&scope=r_liteprofile%20r_emailaddress%20w_member_social"
    )

def exchange_code_for_token(code: str) -> Dict[str, Any]:
    """Exchange authorization code for access token"""
    url = "https://www.linkedin.com/oauth/v2/accessToken"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        "redirect_uri": settings.LINKEDIN_REDIRECT_URI
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    response = requests.post(url, data=payload, headers=headers)
    response.raise_for_status()
    return response.json()

def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """Refresh the LinkedIn access token"""
    url = "https://www.linkedin.com/oauth/v2/accessToken"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "client_secret": settings.LINKEDIN_CLIENT_SECRET
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    response = requests.post(url, data=payload, headers=headers)
    response.raise_for_status()
    return response.json()
