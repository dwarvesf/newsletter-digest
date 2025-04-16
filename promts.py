def get_extract_articles_prompt(content=None):
    return f"""
    Analyze the following email content and extract information about articles mentioned.
    For each article:
    1. Extract the original title, description (if available), and URL (look for [LINK: url] in the text or <title>,<link>,<description> in content)
    2. Rewrite the title and description in a friendlier, lighter tone with a touch of personal feel
    3. Keep the rewritten content concise and engaging
    4. Restrict the description to be less than 160 characters, and be more to the point
      a. Ignore articles that read like
        i. A GitHub release or update
        ii. A sponsorship or donation request
        iii. An advertisement
      b. Prioritize articles that are news, research papers, or have a significant and unique contribution to the field
      c. Save 0.9 and above for the most relevant articles, following the above guidelines
      d. Use up to 2 decimal places for the relevancy scores

    Email content:
    {content}

    Format the output as a JSON array of objects, each with 'title', 'description', and 'url' keys.
    The 'title' and 'description' should contain the rewritten versions.
    Ensure that the output is valid JSON. If no URL is found for an article, use an empty string for the 'url' value.

    Example of the tone and style for rewritten content:
    Original: "Implementing Machine Learning Models: A Comprehensive Guide"
    Rewritten: "Dive into ML: Your Friendly Guide to Bringing Models to Life!"

    Original: "This article provides a detailed walkthrough of implementing various machine learning models, covering data preparation, model selection, and deployment strategies."
    Rewritten: "Ready to make your ML dreams a reality? We've got you covered with easy steps from prepping your data to picking the perfect model. Let's turn those algorithms into action!"
    """