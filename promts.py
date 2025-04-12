def get_extract_articles_prompt(content=None, grouped_criteria=None, min_relevancy_score=None):
    return f"""
    Analyze the following email content and extract information about articles mentioned.
    For each article:
    1. Extract the original title, description (if available), and URL (look for [LINK: url] in the text or <title>,<link>,<description> in content)
    2. Rewrite the title and description in a friendlier, lighter tone with a touch of personal feel
    3. Keep the rewritten content concise and engaging
    4. Restrict the description to be less than 160 characters, and be more to the point
    5. Generate an array of criteria that the article matches, along with a relevancy score (0-1) for each individual criterion
      a. Ignore articles that read like
        i. A GitHub release or update
        ii. A sponsorship or donation request
        iii. An advertisement
      b. Prioritize articles that are news, research papers, or have a significant and unique contribution to the field
      c. Save 0.9 and above for the most relevant articles, following the above guidelines
      d. Use up to 2 decimal places for the relevancy scores
    6. Only include criteria with relevancy scores above {min_relevancy_score}
    
    Email content:
    {content}

    Format the output as a JSON array of objects, each with 'title', 'description', 'url', and 'criteria' keys.
    The 'title' and 'description' should contain the rewritten versions.
    The 'criteria' should be an array of objects, each with 'name' and 'score' keys.
    Ensure that the output is valid JSON. If no URL is found for an article, use an empty string for the 'url' value.

    Use the following list of criteria, but return them as individual items, not grouped:
    {grouped_criteria}

    Example of the tone and style for rewritten content:
    Original: "Implementing Machine Learning Models: A Comprehensive Guide"
    Rewritten: "Dive into ML: Your Friendly Guide to Bringing Models to Life!"

    Original: "This article provides a detailed walkthrough of implementing various machine learning models, covering data preparation, model selection, and deployment strategies."
    Rewritten: "Ready to make your ML dreams a reality? We've got you covered with easy steps from prepping your data to picking the perfect model. Let's turn those algorithms into action!"

    Example of criteria output:
    "criteria": [
        {{"name": "Typescript", "score": 0.95}},
        {{"name": "Javascript", "score": 0.90}},
        {{"name": "React", "score": 0.80}}
    ]
    """