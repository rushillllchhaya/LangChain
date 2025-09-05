import requests
import base64
import os
import json
import re
from urllib.parse import quote

class GitHubReadmeExtractor:
    def __init__(self, token=None):
        """
        Initialize the extractor with optional GitHub token for better rate limits
        
        Args:
            token (str): GitHub personal access token (optional)
        """
        self.base_url = "https://api.github.com"
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'README-Extractor'
        }
        
        if token:
            self.headers['Authorization'] = f'token {token}'
    
    def get_repo_contents(self, owner, repo, path=""):
        """
        Get contents of a repository folder
        
        Args:
            owner (str): Repository owner
            repo (str): Repository name  
            path (str): Path within the repository
            
        Returns:
            list: List of file/folder information
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{quote(path)}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching contents for {path}: {e}")
            return []
    
    def generate_filename_from_content(self, content, original_path, max_words=4):
        """
        Generate a meaningful filename based on README content
        
        Args:
            content (str): README file content
            original_path (str): Original file path for fallback
            max_words (int): Maximum number of words to use in filename
            
        Returns:
            str: Generated filename
        """
        if not content:
            return self.sanitize_filename(original_path.replace('/', '_'))
        
        # Try to extract title from various sources
        title_candidates = []
        
        # Look for markdown headers (# Title)
        header_match = re.search(r'^#+\s*(.+?)$', content, re.MULTILINE)
        if header_match:
            title_candidates.append(header_match.group(1).strip())
        
        # Look for HTML title tags
        html_title_match = re.search(r'<h[1-6][^>]*>(.*?)</h[1-6]>', content, re.IGNORECASE | re.DOTALL)
        if html_title_match:
            # Remove HTML tags from title
            clean_title = re.sub(r'<[^>]+>', '', html_title_match.group(1)).strip()
            if clean_title:
                title_candidates.append(clean_title)
        
        # Look for project name in package.json style comments or descriptions
        desc_match = re.search(r'(?:description|about|project):\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
        if desc_match:
            title_candidates.append(desc_match.group(1).strip())
        
        # Fallback: use first meaningful sentence
        if not title_candidates:
            # Remove markdown syntax and get first line with content
            clean_content = re.sub(r'[#*`\[\]()_~]', '', content)
            lines = [line.strip() for line in clean_content.split('\n') if line.strip()]
            if lines:
                first_line = lines[0]
                # Take first sentence or first 50 characters
                sentence_end = re.search(r'[.!?]', first_line)
                if sentence_end and sentence_end.start() < 50:
                    title_candidates.append(first_line[:sentence_end.start()])
                else:
                    title_candidates.append(first_line[:50])
        
        # Process the best title candidate
        if title_candidates:
            title = title_candidates[0]
            # Clean and truncate title
            title = re.sub(r'[^\w\s-]', '', title)  # Remove special chars except spaces and hyphens
            words = title.split()[:max_words]  # Take first few words
            if words:
                filename = '_'.join(words).lower()
                return self.sanitize_filename(filename)
        
        # Ultimate fallback
        return self.sanitize_filename(original_path.replace('/', '_'))
    
    def sanitize_filename(self, filename):
        """
        Sanitize filename for file system compatibility
        
        Args:
            filename (str): Raw filename
            
        Returns:
            str: Sanitized filename
        """
        # Remove or replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Remove extra spaces and underscores
        filename = re.sub(r'[_\s]+', '_', filename)
        # Remove leading/trailing underscores
        filename = filename.strip('_')
        # Ensure it's not empty
        if not filename:
            filename = "readme"
        return filename

    def download_file_content(self, download_url):
        """
        Download file content from GitHub
        
        Args:
            download_url (str): Direct download URL for the file
            
        Returns:
            str: File content
        """
        try:
            response = requests.get(download_url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Error downloading file: {e}")
            return None
    
    def find_readme_files(self, owner, repo, folder_path="", recursive=True):
        """
        Find all README.md files in a specific folder
        
        Args:
            owner (str): Repository owner
            repo (str): Repository name
            folder_path (str): Specific folder path to search in
            recursive (bool): Whether to search recursively in subfolders
            
        Returns:
            list: List of README.md file information
        """
        readme_files = []
        
        def search_folder(path):
            contents = self.get_repo_contents(owner, repo, path)
            
            if not contents:
                return
                
            for item in contents:
                if item['type'] == 'file' and item['name'].lower() == 'readme.md':
                    readme_files.append({
                        'name': item['name'],
                        'path': item['path'],
                        'download_url': item['download_url'],
                        'size': item['size']
                    })
                elif item['type'] == 'dir' and recursive:
                    search_folder(item['path'])
        
        search_folder(folder_path)
        return readme_files
    
    def extract_readme_files(self, owner, repo, folder_path="", output_dir="extracted_readmes", recursive=True, rename_by_content=True):
        """
        Extract all README.md files from a GitHub repository folder
        
        Args:
            owner (str): Repository owner
            repo (str): Repository name
            folder_path (str): Specific folder path to search in
            output_dir (str): Directory to save extracted README files
            recursive (bool): Whether to search recursively in subfolders
            rename_by_content (bool): Whether to rename files based on their content
            
        Returns:
            dict: Summary of extraction results
        """
        print(f"Searching for README.md files in {owner}/{repo}/{folder_path}")
        
        # Find all README files
        readme_files = self.find_readme_files(owner, repo, folder_path, recursive)
        
        if not readme_files:
            print("No README.md files found in the specified folder.")
            return {'success': False, 'files_extracted': 0, 'files': []}
        
        # Create output directory with absolute path
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        print(f"Output directory: {output_dir}")
        
        extracted_files = []
        success_count = 0
        filename_counts = {}  # Track duplicate filenames
        
        for readme in readme_files:
            print(f"Downloading: {readme['path']}")
            
            # Download content
            content = self.download_file_content(readme['download_url'])
            
            if content:
                # Generate filename based on content or path
                if rename_by_content:
                    base_filename = self.generate_filename_from_content(content, readme['path'])
                else:
                    base_filename = self.sanitize_filename(readme['path'].replace('/', '_'))
                
                # Handle duplicate filenames
                if base_filename in filename_counts:
                    filename_counts[base_filename] += 1
                    final_filename = f"{base_filename}_{filename_counts[base_filename]}.md"
                else:
                    filename_counts[base_filename] = 0
                    final_filename = f"{base_filename}.md"
                
                output_file = os.path.join(output_dir, final_filename)
                
                # Save file
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    extracted_files.append({
                        'original_path': readme['path'],
                        'saved_as': final_filename,
                        'full_path': output_file,
                        'size': readme['size'],
                        'content_preview': content[:100] + '...' if len(content) > 100 else content
                    })
                    success_count += 1
                    print(f"✓ Saved: {final_filename}")
                    
                except Exception as e:
                    print(f"✗ Error saving {readme['path']}: {e}")
            else:
                print(f"✗ Failed to download: {readme['path']}")
        
        # Save summary
        summary = {
            'repository': f"{owner}/{repo}",
            'folder_path': folder_path,
            'output_directory': output_dir,
            'total_found': len(readme_files),
            'successfully_extracted': success_count,
            'extraction_settings': {
                'recursive': recursive,
                'rename_by_content': rename_by_content
            },
            'files': extracted_files
        }
        
        summary_file = os.path.join(output_dir, 'extraction_summary.json')
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\nExtraction complete!")
        print(f"Found: {len(readme_files)} README.md files")
        print(f"Successfully extracted: {success_count} files")
        print(f"Files saved in: {output_dir}")
        print(f"Summary saved as: {summary_file}")
        
        return summary

# Example usage
def main():
    # Initialize extractor (optionally with GitHub token for better rate limits)
    # To get a token: https://github.com/settings/tokens
    extractor = GitHubReadmeExtractor(token=None)  # Add your token here if you have one
    
    # Configuration for AWS Lambda Developer Guide
    owner = "awsdocs"  # Repository owner
    repo = "aws-lambda-developer-guide"      # Repository name
    folder = ""  # Empty string to search entire repository (or specify a folder like "sample-apps")
    
    # SPECIFY YOUR CUSTOM OUTPUT FOLDER HERE
    my_custom_folder = "./data/aws_docs" # Change this to your desired path
    # For Windows: my_custom_folder = r"C:\Users\YourName\Documents\AWSLambdaReadmes"
    # For Mac/Linux: my_custom_folder = "/Users/YourName/Documents/AWSLambdaReadmes"
    
    # Extract README files with content-based renaming
    result = extractor.extract_readme_files(
        owner=owner,
        repo=repo,
        folder_path=folder,
        output_dir=my_custom_folder,  # Your custom folder
        recursive=True,  # Set to False to search only in the specified folder
        rename_by_content=True  # Set to False to use original path-based naming
    )
    
    # Print some example renamed files
    if result['files']:
        print("\nExample renamed files:")
        for file_info in result['files'][:5]:  # Show first 5
            print(f"  {file_info['original_path']} → {file_info['saved_as']}")
    
    return result

# Quick usage function for easy customization
def extract_readmes(owner, repo, folder_path, your_output_folder):
    """
    Quick function to extract README files to your custom folder
    
    Args:
        owner (str): GitHub repo owner
        repo (str): GitHub repo name  
        folder_path (str): Folder within repo to search
        your_output_folder (str): Your local folder path
    """
    extractor = GitHubReadmeExtractor()
    return extractor.extract_readme_files(
        owner=owner,
        repo=repo, 
        folder_path=folder_path,
        output_dir=your_output_folder,
        recursive=True,
        rename_by_content=True
    )

if __name__ == "__main__":
    main()
