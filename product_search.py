from intelligent_search import search_engine

def search_products(query, category=None, in_stock_only=True):
    """Search for products using intelligent semantic search"""
    print(f"DEBUG: product_search.search_products called with query='{query}', category='{category}'")
    
    try:
        # Use the intelligent search engine
        if category:
            # Search within specific category
            results, matched_category = search_engine.search_by_category(category)
            print(f"DEBUG: Category search for '{category}' matched '{matched_category}', found {len(results)} items")
            return results
        else:
            # General search
            results = search_engine.search_products(query)
            print(f"DEBUG: General search for '{query}' found results type: {type(results)}")
            
            # If it's a category listing request, return organized results
            if isinstance(results, dict):
                print(f"DEBUG: Returning dict with categories: {list(results.keys())}")
                return results
            elif isinstance(results, list):
                print(f"DEBUG: Returning list with {len(results)} items")
                return results
            
            return results
            
    except Exception as e:
        print(f"ERROR in intelligent search: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to basic search if needed
        return []

def find_similar_products(product_name, max_results=3):
    """Find similar products using intelligent semantic search"""
    try:
        return search_engine.find_similar_products(product_name, max_results)
    except Exception as e:
        print(f"Error finding similar products: {e}")
        return []

def find_complementary_products(product_name, max_results=2):
    """Find complementary products using intelligent search"""
    try:
        # Use semantic search to find related products
        similar_products = search_engine.find_similar_products(product_name, max_results * 2)
        
        # Filter to get truly complementary items (not just similar)
        complementary = []
        for item in similar_products:
            if product_name.lower() not in item.get('Item Name', '').lower():
                complementary.append(item)
                if len(complementary) >= max_results:
                    break
        
        return complementary
    except Exception as e:
        print(f"Error finding complementary products: {e}")
        return []

def get_categories_summary():
    """Get summary of available categories"""
    try:
        return search_engine.get_categories_summary()
    except Exception as e:
        print(f"Error getting categories: {e}")
        return {}