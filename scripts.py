import requests
import tenacity
from openai import OpenAI
from pygeomodel.config import get_llm_config


class AcademicQueryService:
    def __init__(self, api_key: str = None,
                 modelingContext: str = "",
                 base_url: str = None):
        # Use config if no explicit keys provided
        if api_key is None or base_url is None:
            default_config = get_llm_config()
            api_key = api_key or default_config.openai_api_key
            base_url = base_url or default_config.openai_base_url
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.modelingContext = modelingContext

    async def get_academic_question_answer(self, query: str) -> dict:
        """
        Get answer to an academic question (main public interface).
        """
        paper_list = await self._get_academic_question_answer_list(query)
        question_answer = await self._get_openai_summary(query, paper_list)
        return {
            "question": query,
            "answer": question_answer,
            "paperList": paper_list
        }

    @tenacity.retry(wait=tenacity.wait_fixed(1), stop=tenacity.stop_after_attempt(5))
    async def _get_academic_question_answer_list(self, query: str, page: int = 1, size: int = 10) -> list:
        """Internal: Get paper list using two-step API flow."""
        try:
            # Step 1: Create search thread to get search_id
            search_url = "https://consensus.app/api/threads/"
            search_payload = {
                "user_message": query,
                "is_pro_enabled": False,
                "is_incognito": False,
                "size": size,
                "filters": {},
                "search_mode": "SUMMARY"
            }
            search_headers = {
                'Referer': 'https://consensus.app',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/plain, */*'
            }

            search_response = requests.post(
                search_url, json=search_payload, headers=search_headers, timeout=15)

            if search_response.status_code not in [200, 201]:
                # Fallback to direct query
                return await self._fallback_direct_query(query, page, size)

            search_data = search_response.json()
            search_id = None

            # Try to get search_id from different locations
            if 'search_id' in search_data:
                search_id = search_data['search_id']
            elif 'interactions' in search_data and len(search_data['interactions']) > 0:
                first_interaction = search_data['interactions'][0]
                search_id = first_interaction.get('search_id')

            if not search_id:
                return await self._fallback_direct_query(query, page, size)

            # Step 2: Use search_id to fetch paper results
            papers_url = f"https://consensus.app/api/paper_search/{search_id}/?page={page-1}&size={size}"
            papers_headers = {
                'Referer': 'https://consensus.app',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/json, text/plain, */*'
            }

            papers_response = requests.get(
                papers_url, headers=papers_headers, timeout=15)

            if papers_response.status_code != 200:
                return await self._fallback_direct_query(query, page, size)

            papers_data = papers_response.json()
            papers = papers_data.get("papers", [])

            return papers[:size]

        except Exception as e:
            # Fallback to direct query
            return await self._fallback_direct_query(query, page, size)

    async def _fallback_direct_query(self, query: str, page: int = 1, size: int = 10) -> list:
        """Fallback: Direct paper query (legacy approach)."""
        try:
            url = "https://consensus.app/api/paper_search/?query=" + \
                query + "&page=" + str(page) + "&size=" + str(size)
            payload = {}
            headers = {
                'Referer': 'https://consensus.app',
                'User-Agent': 'Apifox/1.0.0 (https://apifox.com)'
            }
            response = requests.request(
                "GET", url, headers=headers, data=payload).json()

            # return top 10 result in claims
            top10Claims = response["papers"][:10]
            return top10Claims
        except Exception as e:
            return []

    async def _get_openai_summary(self, query: str, paper_list: list) -> str:
        """Internal: Get OpenAI summary of papers."""
        paperContext = ""
        for paper in paper_list:
            # Build context string with paper title, journal, and content
            paperContext += "This is a paper named: " + \
                paper["title"] + " published in: " + paper["journal"] + \
                ". The related content is: " + paper["display_text"] + "."

        completion = self.client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {"role": "system", "content": "You are a helpful AI researcher assistant. User is now conducting scientific geoscience research. The modeling history is: " + self.modelingContext +
                    ". He/she is now asking a question about " + query + ".  And here are some information related to this question: " + paperContext + ". And your task is to summarize the information and answer the question. Please answer the question in English."},
                {
                    "role": "user",
                    "content": "Besides your summary, you should not reply any other information. Below is your answer to the question based on the information provided: "
                }
            ]
        )
        return completion.choices[0].message.content
