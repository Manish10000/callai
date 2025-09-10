import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sheets_handler import get_inventory

def search_products(query, category=None, in_stock_only=True):
    """Search for products in inventory with optional filters"""
    inventory = get_inventory()
    results = []
    query = query.lower()
    
    # Handle special queries
    if any(word in query for word in ["grocery", "items", "products", "available", "present", "list", "show"]):
        # Return all products if asking for general listing
        for item in inventory:
            if in_stock_only and item.get("Quantity", 0) <= 0:
                continue
            if category and item.get("Category", "").lower() != category.lower():
                continue
            results.append(item)
        return results[:10]  # Limit to first 10 items
    
    # First try exact substring matching
    for item in inventory:
        # Check if out of stock
        if in_stock_only and item.get("Quantity", 0) <= 0:
            continue
            
        # Check category filter
        if category and item.get("Category", "").lower() != category.lower():
            continue
            
        # Search in name, description, and tags
        item_text = f"{item.get('Item Name', '')} {item.get('Description', '')} {item.get('Tags', '')}".lower()
        if query in item_text:
            results.append(item)
    
    # If no exact matches, try fuzzy matching with individual words
    if not results:
        query_words = query.split()
        for item in inventory:
            if in_stock_only and item.get("Quantity", 0) <= 0:
                continue
            if category and item.get("Category", "").lower() != category.lower():
                continue
                
            item_text = f"{item.get('Item Name', '')} {item.get('Description', '')} {item.get('Tags', '')}".lower()
            # Check if any query word matches
            for word in query_words:
                if len(word) > 2 and word in item_text:  # Skip very short words
                    results.append(item)
                    break
    
    return results

def find_similar_products(product_name, max_results=3):
    """Find similar products using TF-IDF and cosine similarity"""
    inventory = get_inventory()
    
    # Prepare text data for vectorization
    product_texts = []
    for item in inventory:
        text = f"{item.get('Item Name', '')} {item.get('Category', '')} {item.get('Description', '')} {item.get('Tags', '')}"
        product_texts.append(text)
    
    # Add the search query as a document
    product_texts.append(product_name)
    
    # Create TF-IDF vectors
    vectorizer = TfidfVectorizer(stop_words='english', min_df=1)
    tfidf_matrix = vectorizer.fit_transform(product_texts)
    
    # Find the index of the target product (exact match first)
    target_index = -1
    for i, item in enumerate(inventory):
        if product_name.lower() in item.get('Item Name', '').lower():
            target_index = i
            break
    
    # If no exact match, use the query vector (last item)
    if target_index == -1:
        target_index = len(inventory)  # Index of the query vector
    
    # Calculate cosine similarities
    cosine_similarities = cosine_similarity(tfidf_matrix[target_index], tfidf_matrix).flatten()
    
    # Get indices of most similar products (excluding the target itself if it's a product)
    if target_index < len(inventory):
        # Exclude the target product itself
        similar_indices = cosine_similarities.argsort()[::-1][1:max_results+1]
    else:
        # Include all products, sorted by similarity
        similar_indices = cosine_similarities[:-1].argsort()[::-1][:max_results]
    
    # Return similar products
    similar_products = []
    for idx in similar_indices:
        if idx < len(inventory) and inventory[idx].get('Quantity', 0) > 0:  # Only suggest in-stock items
            similar_products.append(inventory[idx])
    
    return similar_products

def find_complementary_products(product_name, max_results=2):
    """Find complementary products based on category and tags"""
    inventory = get_inventory()
    target_product = None
    
    # Find the target product
    for item in inventory:
        if product_name.lower() in item.get('Item Name', '').lower():
            target_product = item
            break
    
    if not target_product:
        return []
    
    # Find complementary products (same category or matching tags)
    complementary = []
    for item in inventory:
        # Skip the target product and out-of-stock items
        if item.get('Item Name', '') == target_product.get('Item Name', '') or item.get('Quantity', 0) <= 0:
            continue
        
        # Check if same category or shared tags
        target_tags = set(target_product.get('Tags', '').lower().split(','))
        item_tags = set(item.get('Tags', '').lower().split(','))
        
        if (item.get('Category', '') == target_product.get('Category', '') or 
            len(target_tags.intersection(item_tags)) > 0):
            complementary.append(item)
            
            if len(complementary) >= max_results:
                break
    
    return complementary