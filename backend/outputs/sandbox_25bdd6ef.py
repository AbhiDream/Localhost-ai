def two_sum(arr, target):
    # Create a dictionary to store the indices of the elements
    num_to_index = {}
    
    # Iterate through the array
    for i, num in enumerate(arr):
        # Calculate the complement that would add up to the target
        complement = target - num
        
        # Check if the complement is already in the dictionary
        if complement in num_to_index:
            # Return the indices of the current element and its complement
            return (num_to_index[complement], i)
        
        # Store the current element and its index in the dictionary
        num_to_index[num] = i
    
    # If no solution is found, return an empty tuple
    return ()

# Sample usage
arr = [2, 7, 11, 15]
target = 9
result = two_sum(arr, target)
print(result)  # Output: (0, 1)