function previewImages(input) {
    const preview = document.getElementById('imagePreview');
    preview.innerHTML = '';
    
    if (input.files) {
        Array.from(input.files).forEach(file => {
            const reader = new FileReader();
            reader.onload = function(e) {
                const div = document.createElement('div');
                div.innerHTML = `
                    <img src="${e.target.result}" class="img-thumbnail" style="height: 100px;">
                `;
                preview.appendChild(div);
            }
            reader.readAsDataURL(file);
        });
    }
}

function previewMedia(input) {
    const preview = document.getElementById('mediaPreview');
    
    if (input.files) {
        if (input.files.length > 5) {
            alert('Maximum 5 files allowed');
            input.value = '';
            return;
        }
        
        preview.innerHTML = ''; // Clear existing previews
        
        Array.from(input.files).forEach((file, index) => {
            const reader = new FileReader();
            reader.onload = function(e) {
                const div = document.createElement('div');
                div.className = 'media-preview-wrapper';
                
                const mediaHtml = file.type.startsWith('image/') 
                    ? `<img src="${e.target.result}" class="media-preview" alt="Preview">` 
                    : `<video src="${e.target.result}" class="media-preview" controls></video>`;
                
                div.innerHTML = `
                    <div class="media-preview-item">
                        ${mediaHtml}
                        <button type="button" class="remove-media" onclick="removeMedia(${index}, this)">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                `;
                preview.appendChild(div);
            }
            reader.readAsDataURL(file);
        });
    }
}

function removeMedia(index, button) {
    const mediaInput = document.getElementById('reviewMedia');
    const preview = document.getElementById('mediaPreview');
    
    // Remove preview element
    button.closest('.media-preview-wrapper').remove();
    
    // Create new FileList without removed file
    const dt = new DataTransfer();
    const files = Array.from(mediaInput.files);
    files.splice(index, 1);
    files.forEach(file => dt.items.add(file));
    mediaInput.files = dt.files;
}

function submitReview(event) {
    event.preventDefault();
    
    const form = event.target.closest('form');
    const formData = new FormData(form);
    const productId = document.getElementById('productId').value;
    const rating = document.getElementById('selectedRating').value;
    const comment = document.getElementById('reviewComment').value;
    const mediaFiles = document.getElementById('reviewMedia')?.files;
    
    // Validate inputs
    if (!rating) {
        showToast('error', 'Please select a rating');
        return;
    }
    
    if (!comment.trim()) {
        showToast('error', 'Please write a review comment');
        return;
    }
    
    // Handle file uploads
    if (mediaFiles && mediaFiles.length > 0) {
        Array.from(mediaFiles).forEach(file => {
            formData.append('images[]', file);
        });
    }
    
    // Disable submit button and show loading state
    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Submitting...';
    
    // Get CSRF token - try both meta tag and form input
    let csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    if (!csrfToken) {
        csrfToken = document.querySelector('input[name="csrf_token"]')?.value;
    }
    
    // Add CSRF token to form data
    formData.append('csrf_token', csrfToken);
    
    fetch(`/product/${productId}/review`, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRF-Token': csrfToken
        },
        body: formData
    })
    .then(async response => {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return response.json().then(data => {
                if (!response.ok) {
                    throw new Error(data.error || 'Failed to submit review');
                }
                return data;
            });
        } else {
            // If response is not JSON, get the text and throw an error
            const text = await response.text();
            if (text.includes('<!DOCTYPE html>')) {
                // If we got an HTML response, user might be logged out
                throw new Error('Your session may have expired. Please refresh the page and try again.');
            } else {
                throw new Error('Unexpected server response. Please try again.');
            }
        }
    })
    .then(data => {
        showToast('success', 'Review submitted successfully!');
        
        // Close modal and refresh page after delay
        setTimeout(() => {
            const modal = bootstrap.Modal.getInstance(document.getElementById('reviewModal'));
            modal.hide();
            window.location.reload();
        }, 1500);
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('error', error.message || 'Error submitting review');
        
        // If it's a session error, reload the page after a delay
        if (error.message.includes('session may have expired')) {
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        }
    })
    .finally(() => {
        submitBtn.disabled = false;
        submitBtn.innerHTML = 'Submit Review';
    });
}

function showToast(type, message) {
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'success' ? 'success' : 'danger'} border-0 shadow`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'} me-2"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    document.body.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
} 