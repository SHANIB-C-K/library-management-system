document.addEventListener('DOMContentLoaded', () => {
    // Initialize AOS animations
    AOS.init({
        duration: 800,
        once: true,
        offset: 50
    });

    // Initialize Lucide icons
    lucide.createIcons();

    // Setup global dialog closing logic (click outside to close)
    const dialogs = document.querySelectorAll('dialog');
    dialogs.forEach(dialog => {
        dialog.addEventListener('click', (e) => {
            const dialogDimensions = dialog.getBoundingClientRect()
            if (
                e.clientX < dialogDimensions.left ||
                e.clientX > dialogDimensions.right ||
                e.clientY < dialogDimensions.top ||
                e.clientY > dialogDimensions.bottom
            ) {
                dialog.close();
            }
        })
    });
});

// Utility function to confirm deletions with SweetAlert2
function confirmDeletion(url, title = 'Are you sure?', text = "You won't be able to revert this!") {
    Swal.fire({
        title: title,
        text: text,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#ef4444',
        cancelButtonColor: '#3b82f6',
        confirmButtonText: 'Yes, delete it!',
        background: '#1e293b',
        color: '#fff'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(url, {
                method: 'POST',
            }).then(response => response.json())
              .then(data => {
                  if (data.success) {
                      Swal.fire({
                          title: 'Deleted!',
                          text: 'Record has been deleted.',
                          icon: 'success',
                          background: '#1e293b',
                          color: '#fff'
                      }).then(() => {
                          window.location.reload();
                      });
                  } else {
                      Swal.fire({
                          title: 'Error!',
                          text: data.message || 'Something went wrong.',
                          icon: 'error',
                          background: '#1e293b',
                          color: '#fff'
                      });
                  }
              }).catch(err => {
                  console.error(err);
                  Swal.fire('Error', 'Network error occurred.', 'error');
              });
        }
    });
}
