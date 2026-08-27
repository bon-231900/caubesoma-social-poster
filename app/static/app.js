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
        google_action_url: 'https://roots.vn',
        action: 'now',
        scheduled_time: ''
      },

      aiForm: {
        prompt: '',
        brand_voice: 'Thân thiện',
        model_name: 'gemini-3.5-flash-lite',
        include_emojis: true,
        generate_hashtags: true
      },

      bulkForm: {
        file: null,
        fileName: ''
      },
      bulkPreviewPosts: [],

      metaStatus: {
        facebook: { connected: false, name: '', id: '', message: '' },
        instagram: { connected: false, username: '', id: '', message: '' }
      },

      metaExchange: {
        app_id: '2039281703363967',
        app_secret: '',
        short_token: '',
        isExchanging: false,
        exchangeResult: null
      },

      settingsForm: {
        fb_page_id: '',
        fb_page_access_token: '',
        has_fb_page_access_token: false,
        ig_business_account_id: '',
        imgbb_api_key: '',
        has_imgbb_api_key: false,
        gemini_api_key: '',
        has_gemini_api_key: false,
        gemini_model: 'gemini-3.5-flash-lite',
        google_client_id: '',
        google_client_secret: '',
        has_google_client_secret: false,
        google_connected: false,
        google_location_name: '',
        google_location_id: '',
        app_password: ''
      },

      scheduledPosts: [],
      historyPosts: [],

      // ROOTS 1-Click State
      rootsCategories: [],
      selectedRootsCategory: '',
      rootsProducts: [],
      rootsPage: 1,
      rootsPageSize: 20,
      rootsSearchQuery: '',
      isLoadingRoots: false,
      isGeneratingPost: false,
      rootsFlashSaleDiscount: '30%',
      isGeneratingFlashSale: false,
      flashSaleStats: { selectedCount: 0, previewCount: 0 },

      // Media Library State
      mediaItems: [],
      selectedMediaTag: 'all',
      mediaSearchQuery: '',
      mediaFilterMode: 'all',
      mediaPage: 1,
      mediaPageSize: 40,
      isLoadingMedia: false,
      selectedLibraryImage: null,
      customTagInput: '',

      // Templates & Hashtags State
      hashtagGroups: [],
      captionTemplates: [],
      selectedHashtagCategory: 'all',
      selectedTemplateCategory: 'all',
      newHashtagGroup: { name: '', hashtags: '', category: 'Chung' },
      newTemplate: { name: '', content: '', category: 'Sản phẩm', brand_voice: 'Bán hàng' },

      // Calendar State
      calendarEvents: [],
      currentCalendarDate: new Date(),

      // Canvas Studio Modal
      studioModal: {
        show: false,
        fabricCanvas: null,
        preset: 'story',
        currentImageUrl: '',
        activeProduct: null,
        showSafeZone: true,
        safeZoneGroup: null
      },

      // Background Job / Progress
      activeJob: {
        id: null,
        status: '',
        progress: 0,
        current_step: '',
        error: ''
      },
      jobPollInterval: null,

      toast: {
        show: false,
        message: '',
        type: 'info'
      },

      errorModal: {
        show: false,
        content: ''
      }
    };
  },

  async mounted() {
    await this.checkAuth();
  },

  methods: {
    showToast(message, type = 'info') {
      this.toast.message = message;
      this.toast.type = type;
      this.toast.show = true;
      setTimeout(() => {
        this.toast.show = false;
      }, 4000);
    },

    async authFetch(url, options = {}) {
      options.credentials = 'same-origin';
      options.headers = options.headers || {};
      const res = await fetch(url, options);
      if (res.status === 401) {
        this.isAuthenticated = false;
        this.authToken = '';
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
        this.authToken = '';
        this.showToast('Đã đăng xuất', 'info');
      }
    },

    // ── CALENDAR METHODS ──
    async loadCalendarEvents() {
      try {
        const res = await this.authFetch('/api/calendar/events');
        const data = await res.json();
        if (res.ok) {
          this.calendarEvents = data.events || [];
        }
      } catch (err) {
        console.error('Error loading calendar events:', err);
      }
    },
    calendarPrevMonth() {
      const d = new Date(this.currentCalendarDate);
      d.setMonth(d.getMonth() - 1);
      this.currentCalendarDate = d;
    },
    calendarNextMonth() {
      const d = new Date(this.currentCalendarDate);
      d.setMonth(d.getMonth() + 1);
      this.currentCalendarDate = d;
    },
    calendarToday() {
      this.currentCalendarDate = new Date();
    },
    getEventsForDate(dateStr) {
      if (!dateStr || !this.calendarEvents.length) return [];
      return this.calendarEvents.filter(ev => {
        if (!ev.start) return false;
        return ev.start.startsWith(dateStr);
      });
    },

    // ── MEDIA LIBRARY METHODS ──
    async loadMediaLibrary() {
      this.isLoadingMedia = true;
      try {
        let url = `/api/media/library?page=${this.mediaPage}&page_size=${this.mediaPageSize}`;
        if (this.selectedMediaTag && this.selectedMediaTag !== 'all') {
          url += `&tag=${encodeURIComponent(this.selectedMediaTag)}`;
        }
        if (this.mediaSearchQuery) {
          url += `&search=${encodeURIComponent(this.mediaSearchQuery)}`;
        }
        const res = await this.authFetch(url);
        const data = await res.json();
        if (res.ok) {
          this.mediaItems = data.items || [];
        }
      } catch (err) {
        console.error('Error loading media library:', err);
      } finally {
        this.isLoadingMedia = false;
      }
    },
    filterMediaByTag(tag) {
      this.selectedMediaTag = tag;
      this.mediaPage = 1;
      this.loadMediaLibrary();
    },
    filterMediaByAspect(mode) {
      this.mediaFilterMode = mode;
    },
    async uploadFilesToLibrary(e) {
      const files = e.target.files || e.dataTransfer.files;
      if (!files || !files.length) return;
      const formData = new FormData();
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
      }
      try {
        const res = await this.authFetch('/api/media/upload', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.showToast(`✅ Đã tải lên ${data.files.length} ảnh vào thư viện!`, 'success');
          this.loadMediaLibrary();
        } else {
          this.showToast(data.detail || 'Lỗi tải ảnh', 'error');
        }
      } catch (err) {
        this.showToast('Lỗi upload: ' + err.message, 'error');
      }
    },
    selectMediaForComposer(item) {
      if (!this.postForm.images.includes(item.filename)) {
        this.postForm.images.push(item.filename);
        this.showToast('Đã thêm ảnh vào bài viết!', 'info');
      } else {
        this.showToast('Ảnh này đã có trong bài viết.', 'warning');
      }
      this.activeTab = 'composer';
    },
    async addTagToMediaItem(item) {
      if (!this.customTagInput.trim()) return;
      const newTag = this.customTagInput.trim();
      const tags = [...(item.tags || [])];
      if (!tags.includes(newTag)) {
        tags.push(newTag);
        try {
          const res = await this.authFetch(`/api/media/${item.filename}/tags`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tags })
          });
          if (res.ok) {
            item.tags = tags;
            this.customTagInput = '';
            this.showToast('Đã thêm thẻ tag', 'success');
          }
        } catch (err) {}
      }
    },
    async removeTagFromMediaItem(item, tag) {
      const tags = (item.tags || []).filter(t => t !== tag);
      try {
        const res = await this.authFetch(`/api/media/${item.filename}/tags`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tags })
        });
        if (res.ok) {
          item.tags = tags;
          this.showToast('Đã xóa tag', 'info');
        }
      } catch (err) {}
    },
    async deleteMediaFile(item) {
      if (!confirm(`Xóa ảnh ${item.original_name || item.filename}?`)) return;
      try {
        const res = await this.authFetch(`/api/media/${item.filename}`, { method: 'DELETE' });
        if (res.ok) {
          this.showToast('Đã xóa ảnh khỏi thư viện', 'info');
          this.loadMediaLibrary();
        }
      } catch (err) {}
    },

    // ── TEMPLATES & HASHTAGS METHODS ──
    async loadTemplatesAndHashtags() {
      try {
        const [rHt, rTpl] = await Promise.all([
          this.authFetch('/api/hashtag-groups'),
          this.authFetch('/api/caption-templates')
        ]);
        const dHt = await rHt.json();
        const dTpl = await rTpl.json();
        if (rHt.ok) this.hashtagGroups = dHt.groups || [];
        if (rTpl.ok) this.captionTemplates = dTpl.templates || [];
      } catch (err) {
        console.error('Error loading templates:', err);
      }
    },
    insertVariable(tag) {
      if (this.captionTab === 'fb') {
        this.postForm.fb_caption = (this.postForm.fb_caption || '') + ' ' + tag;
      } else if (this.captionTab === 'ig') {
        this.postForm.ig_caption = (this.postForm.ig_caption || '') + ' ' + tag;
      } else {
        this.postForm.google_caption = (this.postForm.google_caption || '') + ' ' + tag;
      }
    },
    insertHashtagGroup(hashtags) {
      if (!hashtags) return;
      if (this.captionTab === 'fb') {
        this.postForm.fb_caption = (this.postForm.fb_caption || '') + '\n\n' + hashtags;
      } else if (this.captionTab === 'ig') {
        this.postForm.ig_caption = (this.postForm.ig_caption || '') + '\n\n' + hashtags;
      } else {
        this.postForm.google_caption = (this.postForm.google_caption || '') + '\n\n' + hashtags;
      }
      this.showToast('✅ Đã chèn nhóm hashtag', 'success');
    },
    applyCaptionTemplate(content) {
      if (!content) return;
      if (this.captionTab === 'fb') {
        this.postForm.fb_caption = content;
      } else if (this.captionTab === 'ig') {
        this.postForm.ig_caption = content;
      } else {
        this.postForm.google_caption = content;
      }
      this.showToast('✅ Đã áp dụng mẫu nội dung', 'success');
    },
    async saveNewHashtagGroup() {
      try {
        const res = await this.authFetch('/api/hashtag-groups', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.newHashtagGroup)
        });
        if (res.ok) {
          this.showToast('✅ Đã lưu nhóm hashtag mới!', 'success');
          this.newHashtagGroup = { name: '', hashtags: '', category: 'Chung' };
          this.loadTemplatesAndHashtags();
        }
      } catch (err) {
        this.showToast('Lỗi lưu nhóm hashtag', 'error');
      }
    },
    async deleteHashtagGroupItem(id) {
      if (!confirm('Xóa nhóm hashtag này?')) return;
      try {
        const res = await this.authFetch(`/api/hashtag-groups/${id}`, { method: 'DELETE' });
        if (res.ok) {
          this.showToast('Đã xóa nhóm hashtag', 'info');
          this.loadTemplatesAndHashtags();
        }
      } catch (err) {}
    },
    async saveNewCaptionTemplate() {
      try {
        const res = await this.authFetch('/api/caption-templates', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.newTemplate)
        });
        if (res.ok) {
          this.showToast('✅ Đã lưu mẫu nội dung mới!', 'success');
          this.newTemplate = { name: '', content: '', category: 'Sản phẩm', brand_voice: 'Bán hàng' };
          this.loadTemplatesAndHashtags();
        }
      } catch (err) {
        this.showToast('Lỗi lưu mẫu nội dung', 'error');
      }
    },
    async deleteCaptionTemplateItem(id) {
      if (!confirm('Xóa mẫu nội dung này?')) return;
      try {
        const res = await this.authFetch('/api/caption-templates/' + id, { method: 'DELETE' });
        if (res.ok) {
          this.showToast('Đã xóa mẫu nội dung', 'info');
          this.loadTemplatesAndHashtags();
        }
      } catch (err) {}
    },

    // ── ROOTS 1-CLICK POST GENERATION ──
    async generatePostFromProduct(p) {
      if (this.isGeneratingPost) return;
      this.isGeneratingPost = true;
      try {
        const res = await this.authFetch('/api/roots/1click-post', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(p)
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.postForm.fb_caption = data.fb_caption || '';
          this.postForm.ig_caption = data.ig_caption || '';
          this.postForm.google_caption = data.google_caption || '';
          this.postForm.story_hook = data.story_hook || '';
          this.postForm.story_template = data.story_template || 'organic';
          this.postForm.story_link = data.story_link || p.product_url || 'https://roots.vn';
          this.postForm.google_action_url = data.story_link || p.product_url || 'https://roots.vn';
          this.postForm.images = data.images || [];
          this.postForm.story_image = data.story_image || '';
          this.activeTab = 'composer';
          this.showToast('🎉 Đã tạo bài viết và hình ảnh chuẩn ROOTS!', 'success');
        } else {
          this.showToast(data.detail || 'Lỗi tạo bài viết ROOTS', 'error');
        }
      } catch (err) {
        this.showToast('Lỗi: ' + err.message, 'error');
      } finally {
        this.isGeneratingPost = false;
      }
    },

    // ── SUBMIT POST & QUEUE METHODS ──
    async submitPost() {
      if (this.isSubmitting) return;
      this.isSubmitting = true;
      try {
        const payload = {
          fb_caption: this.postForm.fb_caption,
          ig_caption: this.postForm.ig_caption,
          google_caption: this.postForm.google_caption,
          images: this.postForm.images,
          target_fb: this.postForm.target_fb,
          target_ig: this.postForm.target_ig,
          target_story: this.postForm.target_story,
          target_google: this.postForm.target_google,
          google_action_type: this.postForm.google_action_type,
          google_action_url: this.postForm.google_action_url,
          story_image: this.postForm.story_image,
          story_template: this.postForm.story_template,
          story_hook: this.postForm.story_hook,
          story_link: this.postForm.story_link,
          action: this.postForm.action,
          scheduled_time: this.postForm.action === 'schedule' ? this.postForm.scheduled_time : null
        };

        const res = await this.authFetch('/api/posts/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok && (data.success || data.post)) {
          if (data.status === 'pending_approval' || this.currentUserRole === 'staff') {
            this.showToast('📤 Bài viết đã được gửi vào Hàng đợi chờ Admin phê duyệt!', 'success');
            this.activeTab = 'scheduled';
            this.loadPendingPosts();
            this.loadScheduledPosts();
          } else if (this.postForm.action === 'now') {
            this.showToast('🎉 Đã đăng bài thành công lên các nền tảng!', 'success');
            this.activeTab = 'history';
            this.loadHistoryPosts();
          } else {
            this.showToast('⏰ Đã lên lịch đăng bài thành công!', 'success');
            this.activeTab = 'scheduled';
            this.loadScheduledPosts();
          }
          this.loadCalendarEvents();
          this.postForm.images = [];
          this.postForm.fb_caption = '';
          this.postForm.ig_caption = '';
          this.postForm.google_caption = '';
          this.postForm.story_hook = '';
          this.postForm.story_image = '';
        } else {
          throw new Error(data.detail || 'Lỗi xử lý bài viết');
        }
      } catch (err) {
        this.showToast(err.message, 'error');
      } finally {
        this.isSubmitting = false;
      }
    },

    async loadPendingPosts() {
      try {
        const res = await this.authFetch('/api/posts?filter_type=pending');
        const data = await res.json();
        if (res.ok) {
          this.pendingPosts = data.posts || [];
        }
      } catch (e) {}
    },

    async approvePost(postId, action = 'publish_now') {
      if (action === 'publish_now' && !confirm('Bạn có chắc chắn muốn duyệt và xuất bản bài viết này ngay lên mạng xã hội?')) return;
      try {
        const res = await this.authFetch(`/api/posts/${postId}/approve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.showToast(data.message || 'Đã duyệt bài viết thành công!', 'success');
          this.loadPendingPosts();
          this.loadScheduledPosts();
          this.loadHistoryPosts();
          this.loadCalendarEvents();
        } else {
          this.showToast(data.detail || 'Lỗi khi duyệt bài', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi kết nối: ' + e.message, 'error');
      }
    },

    async rejectPost(postId) {
      const reason = prompt('Nhập lý do từ chối bài viết (tùy chọn):', 'Nội dung chưa đạt yêu cầu');
      if (reason === null) return;
      try {
        const res = await this.authFetch(`/api/posts/${postId}/reject`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.showToast('Đã từ chối bài viết', 'info');
          this.loadPendingPosts();
          this.loadScheduledPosts();
          this.loadHistoryPosts();
        } else {
          this.showToast(data.detail || 'Lỗi khi từ chối bài', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi kết nối: ' + e.message, 'error');
      }
    },

    async loadScheduledPosts() {
      try {
        const res = await this.authFetch('/api/posts?filter_type=scheduled');
        const data = await res.json();
        if (res.ok) {
          this.scheduledPosts = data.posts || [];
        }
      } catch (e) {}
    },

    async loadHistoryPosts() {
      try {
        const res = await this.authFetch('/api/posts?filter_type=history');
        const data = await res.json();
        if (res.ok) {
          this.historyPosts = data.posts || [];
        }
      } catch (e) {}
    },

    async publishPostNow(postId) {
      try {
        const res = await this.authFetch(`/api/posts/${postId}/publish-now`, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
          this.showToast('Đang tiến hành đăng bài...', 'info');
          this.loadScheduledPosts();
          this.loadHistoryPosts();
          this.loadCalendarEvents();
        } else {
          this.showToast(data.detail || 'Lỗi đăng bài ngay', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi kết nối', 'error');
      }
    },

    async deletePost(postId) {
      if (!confirm('Bạn có chắc muốn xóa bài viết này?')) return;
      try {
        const res = await this.authFetch(`/api/posts/${postId}`, { method: 'DELETE' });
        if (res.ok) {
          this.showToast('Đã xóa bài viết', 'info');
          this.loadScheduledPosts();
          this.loadHistoryPosts();
          this.loadCalendarEvents();
        }
      } catch (e) {}
    },

    async loadRootsCategories() {
      try {
        const res = await this.authFetch('/api/roots/categories');
        const data = await res.json();
        if (res.ok) {
          this.rootsCategories = data.categories || [];
        }
      } catch (err) {}
    },

    async loadRootsData() {
      this.isLoadingRoots = true;
      try {
        let url = `/api/roots/products?page=${this.rootsPage}&page_size=${this.rootsPageSize}`;
        if (this.selectedRootsCategory) {
          url += `&category=${encodeURIComponent(this.selectedRootsCategory)}`;
        }
        const res = await this.authFetch(url);
        const data = await res.json();
        if (res.ok) {
          this.rootsProducts = data.products || [];
        }
      } catch (err) {
      } finally {
        this.isLoadingRoots = false;
      }
    },

    async loadSettings() {
      try {
        const res = await this.authFetch('/api/settings');
        const data = await res.json();
        if (res.ok) {
          const s = data.settings || data;
          this.settingsForm.fb_page_id = s.fb_page_id || '';
          this.settingsForm.ig_business_account_id = s.ig_business_account_id || '';
          this.settingsForm.google_client_id = s.google_client_id || '';
          this.settingsForm.gemini_model = s.gemini_model || 'gemini-3.5-flash-lite';
          this.settingsForm.google_connected = Boolean(s.google_connected);
          this.settingsForm.google_location_name = s.google_location_name || '';
          this.settingsForm.google_location_id = s.google_location_id || '';
          this.settingsForm.has_fb_page_access_token = Boolean(s.masked_token);
          this.settingsForm.has_imgbb_api_key = Boolean(s.has_imgbb_api_key);
          this.settingsForm.has_gemini_api_key = Boolean(s.has_gemini_api_key);
          this.settingsForm.has_google_client_secret = Boolean(s.has_google_client_secret);

          this.settingsForm.fb_page_access_token = '';
          this.settingsForm.imgbb_api_key = '';
          this.settingsForm.gemini_api_key = '';
          this.settingsForm.google_client_secret = '';
          this.settingsForm.app_password = '';
        }
      } catch (e) {}
    },

    formatDateTime(isoStr) {
      if (!isoStr) return '';
      try {
        return new Date(isoStr).toLocaleString('vi-VN');
      } catch (e) {
        return isoStr;
      }
    },

    truncate(str, n = 80) {
      if (!str) return '';
      return str.length > n ? str.substr(0, n - 1) + '...' : str;
    }
  }
}).mount('#app');
