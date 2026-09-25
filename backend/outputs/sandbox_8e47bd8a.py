def find_duplicates(arr):
    # Initialize an empty list to store duplicates
    duplicates = []
    
    # Iterate over each element in the array
    for i in range(len(arr)):
        # Check if the current element is already in the duplicates list
        if arr[i] in duplicates:
            continue
        # Check if the current element appears more than once in the array
        if arr[i] in arr[i+1:]:
            # Add the element to the duplicates list
            duplicates.append(arr[i])
    
    return duplicates

# Sample usage
sample_array = [4, 5, 6, 4, 7, 5, 8, 9, 6, 10]
result = find_duplicates(sample_array)
print(result)  # Output: [4, 5, 6]