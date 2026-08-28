const { createApp } = Vue;

createApp({
  data() {
    return {
      isAuthenticated: false,
      currentUserRole: 'admin',
      authToken: '',
      loginPassword: '',
      showLoginPassword: false,
      loginError: '',
      isLoggingIn: false,
      pendingPosts: [],

      activeTab: 'composer',
      captionTab: 'fb',
      previewPlatform: 'fb',
      currentIgPreviewIdx: 0,
      isDragging: false,
      isDraggingBulk: false,
      isSubmitting: false,
      isTesting: false,
      isSaving: false,
      isImportingBulk: false,
      isGeneratingStory: false,
      isGeneratingAiHook: false,
      showToken: false,

      postForm: {
        target_fb: true,
        target_ig: true,
        target_story: true,
        target_google: false,
        story_template: 'organic',
        story_hook: '',
        story_link: 'https://roots.vn',
        story_image: '',
        images: [],
        fb_caption: '',
        ig_caption: '',
        google_caption: '',
        google_action_type: 'LEARN_MORE',
        google_action_url: '',
        action: 'now',
        scheduled_time: ''
      },
      bulkPreviewPosts: [],
      scheduledPosts: [],
      historyPosts: [],
      
      settingsForm: {
        fb_page_id: '',
        fb_page_access_token: '',
        ig_business_account_id: '',
        imgbb_api_key: '',
        gemini_api_key: '',
        gemini_model: 'gemini-3.5-flash-lite',
        google_client_id: '',
        google_client_secret: '',
        google_connected: false,
        google_location_name: '',
        google_location_id: '',
        has_fb_page_access_token: false,
        has_imgbb_api_key: false,
        has_gemini_api_key: false,
        has_google_client_secret: false,
        has_admin_password: false,
        has_staff_password: false,
        app_password: '',
        admin_password: '',
        staff_password: '',
        max_upload_mb: 12,
        max_upload_batch_mb: 48,
        media_retention_days: 90
      },

      metaStatus: {
        facebook: { connected: false, page_name: '', page_id: '', picture: '', error: '' },
        instagram: { connected: false, username: '', account_id: '', profile_picture: '', error: '' }
      },

      aiUserHint: '',
      isAiGenerating: false,

      rootsProducts: [],
      rootsCategories: {},
      selectedRootsCategory: 'all',
      rootsSearchQuery: '',
      isLoadingRoots: false,
      isGenerating1Click: false,
      generatingProductId: null,
      rootsPagination: {
        current_page: 1,
        total_pages: 1,
        total_items: 0
      },
      selectedComboProducts: [],

      mediaLibrary: [],
      selectedMediaTag: 'all',
      mediaSearchQuery: '',
      isLoadingMedia: false,

      hashtagGroups: [],
      selectedHashtagGroupId: '',
      newHashtagName: '',
      newHashtagContent: '',
      newHashtagCategory: 'Hữu cơ',

      captionTemplates: [],
      selectedTemplateId: '',
      newTemplateName: '',
      newTemplateContent: '',
      newTemplateCategory: 'Sản phẩm',
      newTemplateVoice: 'Bán hàng',

      calendarEvents: [],
      selectedCalendarPost: null,

      toast: {
        show: false,
        message: '',
        type: 'success'
      }
    };
  },

  async mounted() {
    await this.checkAuth();
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(9, 0, 0, 0);
    this.postForm.scheduled_time = tomorrow.toISOString().slice(0, 16);
  },

  methods: {
    async authFetch(url, options = {}) {
      if (!options.headers) options.headers = {};
      options.credentials = 'same-origin';
      const res = await fetch(url, options);
      if (res.status === 401) {
        this.isAuthenticated = false;
      }
      return res;
    },

    async checkAuth() {
      try {
        const res = await fetch('/api/auth/check', { credentials: 'same-origin' });
        if (res.ok) {
          const data = await res.json();
          if (data.authenticated) {
            this.isAuthenticated = true;
            this.currentUserRole = data.role || 'staff';
            if (this.currentUserRole === 'admin') {
              this.loadSettings();
            }
            this.loadScheduledPosts();
            this.loadPendingPosts();
            this.loadRootsCategories();
            this.loadRootsData();
            this.loadMediaLibrary();
            this.loadTemplatesAndHashtags();
            this.loadCalendarEvents();
            return;
          }
        }
        this.isAuthenticated = false;
      } catch (e) {
        this.isAuthenticated = false;
      }
    },

    async handleLogin() {
      this.isLoggingIn = true;
      this.loginError = '';
      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: this.loginPassword })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.isAuthenticated = true;
          this.currentUserRole = data.role || 'staff';
          this.loginPassword = '';
          const roleLabel = this.currentUserRole === 'admin' ? '👑 Quản Trị Viên (Admin)' : '🧑‍💼 Nhân Viên (Staff)';
          this.showToast(`Đăng nhập thành công với quyền ${roleLabel}!`, 'success');
          if (this.currentUserRole === 'admin') {
            this.loadSettings();
          }
          this.loadScheduledPosts();
          this.loadPendingPosts();
          this.loadRootsCategories();
          this.loadRootsData();
          this.loadMediaLibrary();
          this.loadTemplatesAndHashtags();
          this.loadCalendarEvents();
        } else {
          this.loginError = data.detail || 'Mật khẩu không chính xác';
        }
      } catch (err) {
        this.loginError = 'Lỗi kết nối máy chủ: ' + err.message;
      } finally {
        this.isLoggingIn = false;
      }
    },

    async handleLogout() {
      if (confirm('Bạn có chắc chắn muốn đăng xuất?')) {
        try {
          await this.authFetch('/api/auth/logout', { method: 'POST' });
        } catch (e) {}
        this.isAuthenticated = false;
        this.showToast('Đã đăng xuất', 'info');
      }
    },

    showToast(message, type = 'success') {
      this.toast.message = message;
      this.toast.type = type;
      this.toast.show = true;
      setTimeout(() => {
        this.toast.show = false;
      }, 4000);
    },

    // ── UPLOAD IMAGES ──
    async uploadFiles(fileList) {
      if (!fileList || fileList.length === 0) return;
      const formData = new FormData();
      for (let i = 0; i < fileList.length; i++) {
        formData.append('files', fileList[i]);
      }
      try {
        const res = await this.authFetch('/api/upload', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (res.ok && data.success) {
          const filenames = data.filenames || (data.uploaded ? data.uploaded.map(u => u.filename) : []);
          this.postForm.images.push(...filenames);
          this.showToast(`Đã tải lên ${filenames.length} ảnh thành công!`, 'success');
          this.loadMediaLibrary();
        } else {
          this.showToast(data.detail || 'Lỗi tải ảnh', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi kết nối tải ảnh: ' + e.message, 'error');
      }
    },

    handleFileDrop(e) {
      this.isDragging = false;
      if (e.dataTransfer && e.dataTransfer.files) {
        this.uploadFiles(e.dataTransfer.files);
      }
    },

    handleFileInput(e) {
      if (e.target.files) {
        this.uploadFiles(e.target.files);
      }
    },

    removeImage(idx) {
      this.postForm.images.splice(idx, 1);
    },

    getMediaUrl(filename) {
      if (!filename) return '';
      if (filename.startsWith('http://') || filename.startsWith('https://')) return filename;
      return `/api/media/${filename}`;
    },

    // ── ROOTS CATALOG METHODS ──
    async loadRootsCategories() {
      try {
        const res = await this.authFetch('/api/roots/categories');
        const data = await res.json();
        this.rootsCategories = data.categories || {};
      } catch (e) {
        console.error('Error loading roots categories:', e);
      }
    },

    async loadRootsData() {
      this.isLoadingRoots = true;
      try {
        let url = `/api/roots/products?page=${this.rootsPagination.current_page}&page_size=20`;
        if (this.rootsSearchQuery && this.rootsSearchQuery.trim()) {
          url += `&search=${encodeURIComponent(this.rootsSearchQuery.trim())}`;
        }
        if (this.selectedRootsCategory && this.selectedRootsCategory !== 'all') {
          url += `&category=${encodeURIComponent(this.selectedRootsCategory)}`;
        }
        const res = await this.authFetch(url);
        const data = await res.json();
        this.rootsProducts = data.data || data.products || [];
        if (data.pagination) {
          this.rootsPagination = data.pagination;
        }
      } catch (e) {
        this.showToast('Không thể tải sản phẩm từ ROOTS.vn', 'error');
      } finally {
        this.isLoadingRoots = false;
      }
    },

    changeRootsPage(p) {
      if (p < 1 || (this.rootsPagination.total_pages && p > this.rootsPagination.total_pages)) return;
      this.rootsPagination.current_page = p;
      this.loadRootsData();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    getRootsImageUrl(img) {
      if (!img) return 'https://roots.vn/themes/roots/assets/images/no-image.png';
      if (img.startsWith('http://') || img.startsWith('https://')) return img;
      return `https://img.roots.vn/products/${img.split('?')[0]}`;
    },

    formatRootsPrice(val) {
      const num = parseFloat(val || 0);
      if (num <= 0) return 'Liên hệ';
      return num.toLocaleString('vi-VN') + 'đ';
    },

    hasDiscount(p) {
      const gKm = parseFloat(p.GiaSauKm || p.gia || 0);
      const gOld = parseFloat(p.GiaTruocKm || p.gia_goc || 0);
      return gOld > gKm && gKm > 0;
    },

    calcDiscountPercent(p) {
      const gKm = parseFloat(p.GiaSauKm || p.gia || 0);
      const gOld = parseFloat(p.GiaTruocKm || p.gia_goc || 0);
      if (gOld <= gKm || gOld <= 0) return 0;
      return Math.round(((gOld - gKm) / gOld) * 100);
    },

    async quickGenerateRootsPost(product) {
      this.generatingProductId = product.id;
      this.isGenerating1Click = true;
      try {
        const res = await this.authFetch('/api/roots/quick-generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ product: product, aspect_ratio: '4:5' })
        });
        const d = await res.json();
        if (res.ok && d.success) {
          const generated = d.data;
          this.postForm.images = [generated.feed_image];
          this.postForm.fb_caption = generated.fb_caption;
          this.postForm.ig_caption = generated.ig_caption;
          this.postForm.google_caption = generated.google_caption;
          this.postForm.story_image = generated.story_image;
          this.postForm.story_template = generated.story_template;
          this.postForm.story_hook = generated.story_hook;
          this.postForm.story_link = generated.story_link;
          this.postForm.target_story = true;
          this.activeTab = 'composer';
          this.showToast(`✨ Đã tạo xong ảnh Studio 4:5, Story 9:16 & Caption AI cho ${product.TenSanPham || product.ten_san_pham}!`, 'success');
        } else {
          this.showToast(d.detail || 'Lỗi tạo bài tự động', 'error');
        }
      } catch (err) {
        this.showToast('Lỗi kết nối khi tạo bài: ' + err.message, 'error');
      } finally {
        this.isGenerating1Click = false;
        this.generatingProductId = null;
      }
    },

    // ── AI CAPTION ──
    async generateAICaption() {
      this.isAiGenerating = true;
      try {
        const res = await this.authFetch('/api/ai/generate-caption', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ images: this.postForm.images, user_hint: this.aiUserHint })
        });
        const data = await res.json();
        if (res.ok && data.data) {
          this.postForm.fb_caption = data.data.facebook || '';
          this.postForm.ig_caption = data.data.instagram || '';
          this.postForm.google_caption = data.data.google || '';
          if (data.data.story_hook) {
            this.postForm.story_hook = data.data.story_hook;
          }
          this.showToast('✨ Đã tạo xong Caption thông minh bằng Gemini AI!', 'success');
        } else {
          this.showToast(data.detail || 'Lỗi tạo Caption AI', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi kết nối AI: ' + e.message, 'error');
      } finally {
        this.isAiGenerating = false;
      }
    },

    // ── SUBMIT POST ──
    async submitPost() {
      if (!this.postForm.fb_caption && !this.postForm.ig_caption && !this.postForm.google_caption) {
        this.showToast('Vui lòng nhập nội dung bài viết.', 'error');
        return;
      }
      this.isSubmitting = true;
      try {
        const res = await this.authFetch('/api/posts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.postForm)
        });
        const data = await res.json();
        if (res.ok && (data.success || data.post)) {
          if (this.currentUserRole === 'staff') {
            this.showToast('✅ Đã gửi bài vào Hàng đợi chờ Admin phê duyệt!', 'success');
          } else if (this.postForm.action === 'now') {
            this.showToast('🚀 Đã xuất bản bài viết thành công!', 'success');
          } else {
            this.showToast('📅 Đã lên lịch đăng bài tự động!', 'success');
          }
          this.loadScheduledPosts();
          this.loadPendingPosts();
          this.loadCalendarEvents();
        } else {
          this.showToast(data.detail || 'Lỗi gửi bài', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi máy chủ khi gửi bài: ' + e.message, 'error');
      } finally {
        this.isSubmitting = false;
      }
    },

    // ── SETTINGS & GOOGLE CONNECT ──
    async loadSettings() {
      try {
        const res = await this.authFetch('/api/settings');
        if (res.ok) {
          const data = await res.json();
          this.settingsForm = { ...this.settingsForm, ...data };
          if (this.settingsForm.fb_page_id && this.settingsForm.masked_token) {
            this.testSettingsConnection();
          }
        }
      } catch (e) {
        console.error('Error loading settings:', e);
      }
    },

    async saveSettings() {
      this.isSaving = true;
      try {
        const res = await this.authFetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.settingsForm)
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.showToast('✅ Đã lưu cài đặt hệ thống thành công!', 'success');
          this.loadSettings();
        } else {
          this.showToast(data.detail || 'Lỗi lưu cài đặt', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi máy chủ: ' + e.message, 'error');
      } finally {
        this.isSaving = false;
      }
    },

    async testSettingsConnection() {
      this.isTesting = true;
      try {
        const res = await this.authFetch('/api/settings/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            fb_page_id: this.settingsForm.fb_page_id,
            fb_page_access_token: this.settingsForm.fb_page_access_token,
            ig_business_account_id: this.settingsForm.ig_business_account_id
          })
        });
        const data = await res.json();
        if (data.facebook) this.metaStatus.facebook = data.facebook;
        if (data.instagram) this.metaStatus.instagram = data.instagram;
        if (data.facebook && data.facebook.connected) {
          this.showToast(`✅ Đã liên kết Fanpage: ${data.facebook.page_name}!`, 'success');
        }
      } catch (e) {
        console.error('Error testing connection:', e);
      } finally {
        this.isTesting = false;
      }
    },

    async connectGoogle() {
      try {
        const res = await this.authFetch('/api/google/auth-url');
        const data = await res.json();
        if (res.ok && data.auth_url) {
          window.location.href = data.auth_url;
        } else {
          this.showToast(data.detail || 'Vui lòng nhập Google Client ID & Secret trước.', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi kết nối Google: ' + e.message, 'error');
      }
    },

    // ── MEDIA, CALENDAR, QUEUE HELPERS ──
    async loadMediaLibrary() {
      try {
        const res = await this.authFetch('/api/media/library');
        const data = await res.json();
        this.mediaLibrary = data.media || [];
      } catch (e) {}
    },
    async loadScheduledPosts() {
      try {
        const res = await this.authFetch('/api/posts?filter_type=scheduled');
        const data = await res.json();
        this.scheduledPosts = data.posts || [];
      } catch (e) {}
    },
    async loadPendingPosts() {
      try {
        const res = await this.authFetch('/api/posts?filter_type=pending');
        const data = await res.json();
        this.pendingPosts = data.posts || [];
      } catch (e) {}
    },
    async loadCalendarEvents() {
      try {
        const res = await this.authFetch('/api/calendar/events');
        const data = await res.json();
        this.calendarEvents = data.events || [];
      } catch (e) {}
    },
    async loadTemplatesAndHashtags() {
      try {
        const [hRes, tRes] = await Promise.all([
          this.authFetch('/api/hashtag-groups'),
          this.authFetch('/api/caption-templates')
        ]);
        const hData = await hRes.json();
        const tData = await tRes.json();
        this.hashtagGroups = hData.groups || [];
        this.captionTemplates = tData.templates || [];
      } catch (e) {}
    },
    async approvePendingPost(post, action = 'publish_now') {
      try {
        const res = await this.authFetch(`/api/posts/${post.id}/approve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: action })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.showToast(data.message || 'Đã duyệt bài thành công!', 'success');
          this.loadPendingPosts();
          this.loadScheduledPosts();
        }
      } catch (e) {}
    },
    async rejectPendingPost(post) {
      const reason = prompt('Nhập lý do từ chối:');
      if (reason === null) return;
      try {
        const res = await this.authFetch(`/api/posts/${post.id}/reject`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: reason })
        });
        if (res.ok) {
          this.showToast('Đã từ chối bài viết', 'info');
          this.loadPendingPosts();
        }
      } catch (e) {}
    },
    async publishNow(id) {
      try {
        const res = await this.authFetch(`/api/posts/${id}/publish-now`, { method: 'POST' });
        if (res.ok) {
          this.showToast('🚀 Đã xuất bản bài viết!', 'success');
          this.loadScheduledPosts();
        }
      } catch (e) {}
    },
    async deleteScheduledPost(id) {
      if (!confirm('Xóa bài viết này?')) return;
      try {
        const res = await this.authFetch(`/api/posts/${id}`, { method: 'DELETE' });
        if (res.ok) {
          this.showToast('Đã xóa bài viết', 'info');
          this.loadScheduledPosts();
        }
      } catch (e) {}
    },
    insertVariable(key) {
      const tag = `{${key}}`;
      this.postForm.fb_caption = (this.postForm.fb_caption || '') + ' ' + tag;
      this.postForm.ig_caption = (this.postForm.ig_caption || '') + ' ' + tag;
    },
    getFbName() {
      return this.metaStatus.facebook.page_name || 'ROOTS - Organic Store & Juice Bar';
    },
    getFbPic() {
      return this.metaStatus.facebook.picture || this.metaStatus.instagram.profile_picture || '';
    }
  }
}).mount('#app');
