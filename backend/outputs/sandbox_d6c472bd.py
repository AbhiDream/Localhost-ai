def is_palindrome(s):
    # Convert the string to lowercase and remove spaces
    cleaned_string = s.replace(" ", "").lower()
    
    # Initialize two pointers, one at the start and one at the end of the string
    left, right = 0, len(cleaned_string) - 1
    
    # Loop until the two pointers meet in the middle
    while left < right:
        # Compare characters at the left and right pointers
        if cleaned_string[left] != cleaned_string[right]:
            return False
        # Move the pointers towards the center
        left += 1
        right -= 1
    
    # If all characters matched, the string is a palindrome
    return True

# Example usage
sample_string = "A man a plan a canal Panama"
print(is_palindrome(sample_string))  # Output: True