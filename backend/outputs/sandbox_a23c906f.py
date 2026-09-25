from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity):
        # Initialize the cache with the given capacity
        self.capacity = capacity
        self.cache = OrderedDict()

    def get(self, key):
        # Retrieve the value associated with the key
        if key in self.cache:
            # Move the accessed key to the end of the cache
            self.cache.move_to_end(key)
            return self.cache[key]
        else:
            # Return -1 if the key is not found
            return -1

    def put(self, key, value):
        # Insert or update the key-value pair
        if key in self.cache:
            # Update the value for the existing key
            self.cache[key] = value
            # Move the updated key to the end of the cache
            self.cache.move_to_end(key)
        else:
            # Add a new key-value pair
            self.cache[key] = value
            # If the cache exceeds its capacity, remove the least recently used item
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)

# Example usage
cache = LRUCache(2)
cache.put(1, 10)
cache.put(2, 20)
print(cache.get(1))  # Output: 10
cache.put(3, 30)  # Output: Key 2 should now be evicted
print(cache.get(2))  # Output: -1
cache.put(4, 40)  # Output: Key 1 should now be evicted
print(cache.get(1))  # Output: -1
print(cache.get(3))  # Output: 30
print(cache.get(4))  # Output: 40

# Edge case: LRUCache(1)
cache = LRUCache(1)
cache.put(1, 10)
cache.put(2, 20)  # Output: Key 1 should be evicted
print(cache.get(1))  # Output: -1
cache.put(1, 100)  # Output: Key 1 becomes the most recently used and its value becomes 100