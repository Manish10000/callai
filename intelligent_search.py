import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sheets_handler import get_inventory
import re

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("WARNING: sentence-transformers not available, using TF-IDF fallback")

class IntelligentSearch:
    def __init__(self):
        # Use sentence transformers if available, otherwise TF-IDF
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.use_transformers = True
        else:
            self.vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
            self.use_transformers = False
            
        self.inventory_embeddings = None
        self.inventory_data = None
        self.category_embeddings = None
        self.categories = None
        self._initialize_embeddings()
    
    def _initialize_embeddings(self):
        """Initialize embeddings for inventory and categories"""
        try:
            # Force refresh inventory data to ensure consistency
            self.refresh_inventory()
            
        except Exception as e:
            print(f"Error initializing embeddings: {e}")
            import traceback
            traceback.print_exc()
            self.inventory_data = []
            self.inventory_embeddings = np.array([])
    
    def refresh_inventory(self):
        """Refresh inventory data and regenerate embeddings"""
        self.inventory_data = get_inventory()
        print(f"DEBUG: Loaded {len(self.inventory_data)} items for embedding initialization")
        
        # Print first few items for debugging
        for i, item in enumerate(self.inventory_data[:5]):
            print(f"DEBUG: Item {i+1}: {item.get('Item Name', 'N/A')} - Qty: {item.get('Quantity', 0)}")
        
        # Create text representations for each product
        product_texts = []
        categories = set()
        
        for item in self.inventory_data:
            # Combine all searchable text
            text = f"{item.get('Item Name', '')} {item.get('Category', '')} {item.get('Description', '')} {item.get('Tags', '')}"
            product_texts.append(text)
            categories.add(item.get('Category', '').lower())
        
        # Generate embeddings for products
        if self.use_transformers:
            self.inventory_embeddings = self.model.encode(product_texts)
        else:
            # Use TF-IDF as fallback
            self.inventory_embeddings = self.vectorizer.fit_transform(product_texts)
        
        # Generate embeddings for categories
        self.categories = list(categories)
        if self.use_transformers:
            self.category_embeddings = self.model.encode(self.categories)
        else:
            self.category_embeddings = self.vectorizer.transform(self.categories)
        
        print(f"DEBUG: Initialized {'transformer' if self.use_transformers else 'TF-IDF'} embeddings for {len(self.inventory_data)} products and {len(self.categories)} categories")
        print(f"DEBUG: Categories found: {self.categories}")
    
    def search_products(self, query, max_results=10, similarity_threshold=0.1):
        """Search products using semantic similarity"""
        print(f"DEBUG: IntelligentSearch.search_products called with query: '{query}'")
        
        # Refresh inventory to ensure we have latest data
        self.refresh_inventory()
        
        if not self.inventory_data or len(self.inventory_embeddings) == 0:
            print("DEBUG: No inventory data or embeddings available")
            return []
        
        # Handle general listing queries
        listing_keywords = ["items", "products", "available", "present", "list", "show", "what do you have"]
        is_listing_query = any(keyword in query.lower() for keyword in listing_keywords)
        
        # Handle specific category requests
        category_keywords = {
            "grocery": ["grocery", "groceries"],
            "snacks": ["snack", "snacks"],
            "spices": ["spice", "spices"],
            "food": ["food", "foods"]
        }
        
        requested_category = None
        for category, keywords in category_keywords.items():
            if any(keyword in query.lower() for keyword in keywords):
                requested_category = category
                break
        
        print(f"DEBUG: Is listing query: {is_listing_query}, Requested category: {requested_category}")
        
        if requested_category:
            # Return top 5 items from specific category
            result = self._get_top_items_by_category(requested_category, max_items=5)
            print(f"DEBUG: Returning top 5 items from {requested_category}: {len(result)} items")
            return result
        elif is_listing_query:
            # Return products grouped by category
            result = self._get_products_by_category()
            print(f"DEBUG: Returning category-organized results: {list(result.keys()) if result else 'None'}")
            return result
        
        # Generate embedding for the query
        if self.use_transformers:
            query_embedding = self.model.encode([query])
            similarities = cosine_similarity(query_embedding, self.inventory_embeddings)[0]
        else:
            query_embedding = self.vectorizer.transform([query])
            similarities = cosine_similarity(query_embedding, self.inventory_embeddings).flatten()
        
        # Get indices sorted by similarity
        sorted_indices = np.argsort(similarities)[::-1]
        
        print(f"DEBUG: Top 5 similarity scores for '{query}': {similarities[sorted_indices[:5]]}")
        
        # Filter by threshold and stock
        results = []
        for idx in sorted_indices:
            item = self.inventory_data[idx]
            similarity_score = similarities[idx]
            
            print(f"DEBUG: Item '{item.get('Item Name', '')}' - Similarity: {similarity_score:.3f}, Quantity: {item.get('Quantity', 0)}")
            
            # Lower the threshold and include out-of-stock items for debugging
            if similarity_score < 0.1:  # Lower threshold
                break
            
            # Include all items for now to debug
            item['similarity_score'] = similarity_score
            results.append(item)
            
            if len(results) >= max_results:
                break
        
        # Filter out-of-stock items after getting results
        in_stock_results = [item for item in results if item.get('Quantity', 0) > 0]
        print(f"DEBUG: Found {len(results)} total matches, {len(in_stock_results)} in stock")
        
        return in_stock_results
    
    def search_by_category(self, category_query, max_results=10):
        """Search for products by category using semantic similarity"""
        if not self.categories or len(self.category_embeddings) == 0:
            return []
        
        # Find the most similar category
        if self.use_transformers:
            query_embedding = self.model.encode([category_query])
            similarities = cosine_similarity(query_embedding, self.category_embeddings)[0]
        else:
            query_embedding = self.vectorizer.transform([category_query])
            similarities = cosine_similarity(query_embedding, self.category_embeddings).flatten()
        
        best_category_idx = np.argmax(similarities)
        best_category = self.categories[best_category_idx]
        
        # Get products from that category
        results = []
        for item in self.inventory_data:
            if item.get('Category', '').lower() == best_category and item.get('Quantity', 0) > 0:
                results.append(item)
                if len(results) >= max_results:
                    break
        
        return results, best_category
    
    def _get_products_by_category(self):
        """Get products organized by category for general listing"""
        category_products = {}
        
        for item in self.inventory_data:
            if item.get('Quantity', 0) > 0:  # Only in-stock items
                category = item.get('Category', 'Other')
                if category not in category_products:
                    category_products[category] = []
                category_products[category].append(item)
        
        print(f"DEBUG: _get_products_by_category returning: {[(cat, len(items)) for cat, items in category_products.items()]}")
        return category_products
    
    def _get_top_items_by_category(self, requested_category, max_items=5):
        """Get top items from a specific category"""
        category_items = []
        
        # Find items matching the requested category (case-insensitive)
        for item in self.inventory_data:
            if item.get('Quantity', 0) > 0:  # Only in-stock items
                item_category = item.get('Category', '').lower()
                if requested_category.lower() in item_category or item_category in requested_category.lower():
                    category_items.append(item)
        
        # Sort by quantity (most available first) and then by price
        category_items.sort(key=lambda x: (-x.get('Quantity', 0), x.get('Price (USD)', 0)))
        
        # Return top items
        top_items = category_items[:max_items]
        print(f"DEBUG: _get_top_items_by_category for '{requested_category}': found {len(category_items)} total, returning top {len(top_items)}")
        
        return top_items
    
    def find_similar_products(self, product_name, max_results=3):
        """Find products similar to a given product name"""
        if not self.inventory_data:
            return []
        
        # Find the target product first
        target_item = None
        target_idx = -1
        
        for i, item in enumerate(self.inventory_data):
            if product_name.lower() in item.get('Item Name', '').lower():
                target_item = item
                target_idx = i
                break
        
        if target_idx == -1:
            # If no exact match, search semantically
            return self.search_products(product_name, max_results)
        
        # Find similar products using embeddings
        if self.use_transformers:
            target_embedding = self.inventory_embeddings[target_idx].reshape(1, -1)
            similarities = cosine_similarity(target_embedding, self.inventory_embeddings)[0]
        else:
            target_embedding = self.inventory_embeddings[target_idx]
            similarities = cosine_similarity(target_embedding, self.inventory_embeddings).flatten()
        
        # Get most similar products (excluding the target)
        sorted_indices = np.argsort(similarities)[::-1][1:max_results+1]
        
        similar_products = []
        for idx in sorted_indices:
            item = self.inventory_data[idx]
            if item.get('Quantity', 0) > 0:
                similar_products.append(item)
        
        return similar_products
    
    def get_categories_summary(self):
        """Get a summary of available categories"""
        category_counts = {}
        
        for item in self.inventory_data:
            if item.get('Quantity', 0) > 0:
                category = item.get('Category', 'Other')
                category_counts[category] = category_counts.get(category, 0) + 1
        
        return category_counts

# Global instance
search_engine = IntelligentSearch()