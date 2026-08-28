const { createApp } = Vue;

createApp({
  data() {
    return {
      activeTab: 'composer',
      currentUserRole: 'staff',
      isAuthenticated: false,
      authToken: '',
      loginPassword: '',
      loginError: '',
      isLoggingIn: false,
      showLoginPassword: false,

      // TOAST NOTIFICATIONS
      toast: {
        show: false,
        message: '',
        type: 'info'
      },

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

      pendingPosts: [],
      isLoadingPending: false,
      selectedPendingPost: null,

      scheduledPosts: [],
      isLoadingScheduled: false,
      historyPosts: [],
      isLoadingHistory: false,

      aiHint: '',
      isGeneratingAI: false,

      settingsForm: {
        fb_page_id: '',
        fb_page_access_token: '',
        ig_business_account_id: '',
        imgbb_api_key: '',
        has_imgbb_api_key: false,
        app_password: '',
        admin_password: '',
        staff_password: '',
        gemini_api_key: '',
        has_gemini_api_key: false,
        gemini_model: 'gemini-flash-latest',
        google_client_id: '',
        google_client_secret: '',
        google_connected: false,
        google_location_name: '',
        google_location_id: '',
        has_admin_password: true,
        has_staff_password: true,
        has_password: true,
        max_upload_mb: 12,
        max_upload_batch_mb: 48,
        media_retention_days: 90
      },

      metaExchangeForm: {
        short_token: '',
        app_id: '',
        app_secret: '',
        page_id: '',
        isLoading: false,
        error: '',
        result: null
      },

      connectionStatus: {
        facebook: { connected: false, page_name: null, error: null },
        instagram: { connected: false, username: null, error: null }
      },

      storyStudio: {
        selectedImage: '',
        hook: '',
        template: 'organic',
        link: 'https://roots.vn',
        previewUrl: '',
        isGenerating: false
      },

      canvasStudio: {
        canvas: null,
        activeRatio: '4:5',
        activeBackground: 'organic',
        customText: '',
        textFillColor: '#166534',
        safeZoneGroup: null
      },
      studioTemplates: [
        { id: 'organic', name: 'Siêu Thị Hữu Cơ', icon: '🌿' },
        { id: 'juice', name: 'Juice Bar', icon: '🍹' },
        { id: 'sale', name: 'Giờ Vàng Sale', icon: '🔥' },
        { id: 'magazine', name: 'Tạp Chí Ẩm Thực', icon: '✨' },
        { id: 'polaroid', name: 'Chụp Polaroid', icon: '📷' }
      ],

      // ROOTS CATALOG STATE
      rootsProducts: [],
      rootsCategories: {},
      selectedRootsCategory: 'all',
      selectedCreativeRatio: '4:5',
      selectedComboProducts: [],
      comboModal: {
        show: false,
        isLoading: false,
        userHint: '',
        result: null,
        activeCaptionTab: 'fb',
        copiedPromptIdx: null
      },
      rootsSearchQuery: '',
      isFlashSaleOnly: false,
      isLoadingRoots: false,
      isGeneratingPost: false,
      generatingProductId: null,
      rootsPagination: {
        current_page: 1,
        total_pages: 1,
        total_items: 0
      },

      // CONTENT CALENDAR (MIXPOST PATTERN)
      calendarCurrentDate: new Date(),
      calendarEvents: [],
      selectedCalendarPost: null,

      // MEDIA LIBRARY (MIXPOST PATTERN)
      mediaLibrary: [],
      mediaSearch: '',
      selectedMediaTag: 'Tất cả',
      mediaTags: ['Tất cả', 'Trái cây', 'Nước ép', 'Bánh ngọt', 'Chăm sóc', 'Khuyến mãi', 'ROOTS'],
      isLoadingMedia: false,
      selectedMediaFiles: [],
      isBatchDeleting: false,

      // TEMPLATES & HASHTAGS (MIXPOST PATTERN)
      hashtagGroups: [],
      captionTemplates: [],
      selectedHashtagGroupId: '',
      selectedCaptionTemplateId: '',
      selectedBrandVoiceFilter: 'all',
      isCreatingHashtag: false,
      newHashtag: { name: '', hashtags: '', category: 'Chung' },
      isCreatingTemplate: false,
      newTemplate: { name: '', content: '', category: 'Sản phẩm', brand_voice: 'Bán hàng' },

      // BULK EXCEL STATE
      bulkFile: null,
      bulkPosts: [],
      bulkParsedCount: 0,
      isImportingBulkRunning: false,

      // DYNAMIC TEMPLATE VARIABLES
      availableVariables: [
        { key: 'product_name', label: 'Tên sản phẩm', sample: 'Táo Envy Hữu Cơ New Zealand' },
        { key: 'price', label: 'Giá bán', sample: '185.000đ' },
        { key: 'discount', label: 'Mức giảm giá', sample: '(Tiết kiệm 15%)' },
        { key: 'origin', label: 'Xuất xứ', sample: 'New Zealand' },
        { key: 'brand', label: 'Thương hiệu', sample: 'Envy Certified' },
        { key: 'product_url', label: 'Đường dẫn sản phẩm', sample: 'https://roots.vn' },
        { key: 'hotline', label: 'Hotline đặt hàng', sample: '1900 633 463' }
      ]
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
    // ── AUTH METHODS ──
    async authFetch(url, options = {}) {
      if (!options.headers) options.headers = {};
      options.credentials = 'same-origin';
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
    showToast(message, type = 'info') {
      this.toast.message = message;
      this.toast.type = type;
      this.toast.show = true;
      setTimeout(() => {
        this.toast.show = false;
      }, 4500);
    },
    truncate(str, max = 50) {
      if (!str) return '';
      return str.length > max ? str.substring(0, max) + '...' : str;
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
    async loadRootsProducts(p = 1) {
      this.isLoadingRoots = true;
      this.rootsPagination.current_page = p;
      try {
        let url = `/api/roots/products?page=${p}&page_size=20`;
        if (this.rootsSearchQuery && this.rootsSearchQuery.trim()) {
          url += `&search=${encodeURIComponent(this.rootsSearchQuery.trim())}`;
        }
        if (this.selectedRootsCategory && this.selectedRootsCategory !== 'all') {
          url += `&category=${encodeURIComponent(this.selectedRootsCategory)}`;
        }
        const res = await this.authFetch(url);
        const data = await res.json();
        this.rootsProducts = data.products || [];
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
      this.loadRootsProducts(p);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },
    async loadRootsData() {
      await this.loadRootsProducts(1);
    },
    formatRootsPrice(val) {
      if (!val) return '0đ';
      try {
        return Number(val).toLocaleString('vi-VN') + 'đ';
      } catch (e) {
        return val + 'đ';
      }
    },
    hasDiscount(prod) {
      return prod && prod.gia_goc && prod.gia && Number(prod.gia_goc) > Number(prod.gia);
    },
    calcDiscountPercent(prod) {
      if (!this.hasDiscount(prod)) return 0;
      const g = Number(prod.gia_goc);
      const c = Number(prod.gia);
      return Math.round(((g - c) / g) * 100);
    },
    getMediaUrl(filename) {
      if (!filename) return '';
      if (filename.startsWith('http://') || filename.startsWith('https://')) return filename;
      return `/api/media/${filename}`;
    },
    getThumbUrl(filename) {
      if (!filename) return '';
      if (filename.startsWith('http://') || filename.startsWith('https://')) return filename;
      return `/api/media/thumb/${filename}`;
    },

    // ── QUICK 1-CLICK STUDIO METHOD ──
    async quickGenerateRootsPost(product) {
      this.generatingProductId = product.id;
      this.isGeneratingPost = true;
      try {
        const res = await this.authFetch('/api/roots/quick-generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            product: product,
            aspect_ratio: this.selectedCreativeRatio || '4:5'
          })
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
          this.showToast(`✨ Đã tự động tạo ảnh Studio 4:5, Story 9:16 & Caption AI cho ${product.ten_san_pham}!`, 'success');
        } else {
          this.showToast(d.detail || 'Lỗi tạo bài tự động', 'error');
        }
      } catch (err) {
        this.showToast('Lỗi kết nối khi tạo bài: ' + err.message, 'error');
      } finally {
        this.isGeneratingPost = false;
        this.generatingProductId = null;
      }
    },

    // ── COMBO METHODS ──
    toggleComboProduct(product) {
      const idx = this.selectedComboProducts.findIndex(p => p.id === product.id);
      if (idx > -1) {
        this.selectedComboProducts.splice(idx, 1);
      } else {
        if (this.selectedComboProducts.length >= 6) {
          this.showToast('Chỉ nên chọn tối đa 6 sản phẩm trong một combo.', 'info');
          return;
        }
        this.selectedComboProducts.push(product);
      }
    },
    isComboSelected(product) {
      return this.selectedComboProducts.some(p => p.id === product.id);
    },
    openComboModal() {
      if (this.selectedComboProducts.length === 0) {
        this.showToast('Vui lòng chọn ít nhất 1 sản phẩm để tạo combo.', 'info');
        return;
      }
      this.comboModal.show = true;
      this.generateComboCampaign();
    },
    async generateComboCampaign() {
      this.comboModal.isLoading = true;
      this.comboModal.result = null;
      try {
        const res = await this.authFetch('/api/roots/combo-generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            products: this.selectedComboProducts,
            user_hint: this.comboModal.userHint
          })
        });
        const d = await res.json();
        if (res.ok && d.success) {
          this.comboModal.result = d.data;
          this.showToast('✨ Đã tạo chiến dịch Combo AI & Prompt Banner thành công!', 'success');
        } else {
          this.showToast(d.detail || 'Lỗi tạo combo AI', 'error');
        }
      } catch (err) {
        this.showToast('Lỗi kết nối tạo combo: ' + err.message, 'error');
      } finally {
        this.comboModal.isLoading = false;
      }
    },
    applyComboToComposer() {
      if (!this.comboModal.result) return;
      const d = this.comboModal.result;
      this.postForm.fb_caption = d.fb_caption || '';
      this.postForm.ig_caption = d.ig_caption || '';
      this.postForm.google_caption = d.google_caption || '';
      this.postForm.story_hook = d.story_hook || '';
      this.postForm.target_fb = true;
      this.postForm.target_ig = true;
      this.postForm.target_story = true;
      this.postForm.target_google = false;
      this.comboModal.show = false;
      this.activeTab = 'composer';
      this.showToast('Đã áp dụng nội dung Combo vào bộ soạn thảo!', 'success');
    },

    // ── MEDIA LIBRARY METHODS ──
    async loadMediaLibrary() {
      this.isLoadingMedia = true;
      try {
        const tag = this.selectedMediaTag === 'Tất cả' ? 'all' : this.selectedMediaTag;
        const res = await this.authFetch(`/api/media/library?search=${encodeURIComponent(this.mediaSearch)}&tag=${encodeURIComponent(tag)}`);
        const data = await res.json();
        this.mediaLibrary = data.items || [];
      } catch (e) {
        console.error('Error loading media library:', e);
      } finally {
        this.isLoadingMedia = false;
      }
    },
    async uploadFiles(fileList) {
      if (!fileList || fileList.length === 0) return;
      const formData = new FormData();
      for (let i = 0; i < fileList.length; i++) {
        formData.append('files', fileList[i]);
      }
      try {
        const res = await this.authFetch('/api/media/upload', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (res.ok && data.uploaded) {
          this.postForm.images.push(...data.uploaded);
          this.showToast(`Đã tải lên ${data.uploaded.length} ảnh thành công!`, 'success');
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

    // ── AI CAPTION GENERATION ──
    async generateAICaption() {
      if (this.postForm.images.length === 0 && !this.aiHint) {
        this.showToast('Vui lòng tải ảnh lên hoặc nhập gợi ý nội dung.', 'info');
        return;
      }
      this.isGeneratingAI = true;
      try {
        const res = await this.authFetch('/api/ai/generate-caption', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            images: this.postForm.images,
            user_hint: this.aiHint
          })
        });
        const data = await res.json();
        if (res.ok && data.captions) {
          this.postForm.fb_caption = data.captions.facebook || '';
          this.postForm.ig_caption = data.captions.instagram || '';
          this.postForm.google_caption = data.captions.google || '';
          if (data.captions.story_hook) {
            this.postForm.story_hook = data.captions.story_hook;
          }
          this.showToast('✨ Đã tạo xong Caption thông minh bằng Gemini AI!', 'success');
        } else {
          this.showToast(data.detail || 'Lỗi tạo Caption AI', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi kết nối AI: ' + e.message, 'error');
      } finally {
        this.isGeneratingAI = false;
      }
    },

    // ── SUBMIT POST ──
    async submitPost() {
      if (!this.postForm.fb_caption && !this.postForm.ig_caption && !this.postForm.google_caption) {
        this.showToast('Vui lòng nhập nội dung bài viết.', 'error');
        return;
      }
      if (this.postForm.target_ig && this.postForm.images.length === 0) {
        this.showToast('Instagram yêu cầu phải có ít nhất 1 hình ảnh.', 'error');
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
        if (res.ok && data.success) {
          if (this.currentUserRole === 'staff') {
            this.showToast('✅ Đã gửi bài vào Hàng đợi chờ Admin phê duyệt!', 'success');
          } else if (this.postForm.action === 'now') {
            this.showToast('🚀 Đã xuất bản bài viết lên các nền tảng thành công!', 'success');
          } else {
            this.showToast('📅 Đã lên lịch đăng bài tự động!', 'success');
          }
          this.resetPostForm();
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
    resetPostForm() {
      this.postForm = {
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
      };
      this.aiHint = '';
    },

    // ── SCHEDULED & PENDING QUEUE METHODS ──
    async loadScheduledPosts() {
      this.isLoadingScheduled = true;
      try {
        const res = await this.authFetch('/api/posts?filter_type=scheduled');
        const data = await res.json();
        this.scheduledPosts = data.posts || [];
      } catch (e) {
        console.error('Error loading scheduled posts:', e);
      } finally {
        this.isLoadingScheduled = false;
      }
    },
    async loadPendingPosts() {
      this.isLoadingPending = true;
      try {
        const res = await this.authFetch('/api/posts?filter_type=pending');
        const data = await res.json();
        this.pendingPosts = data.posts || [];
      } catch (e) {
        console.error('Error loading pending posts:', e);
      } finally {
        this.isLoadingPending = false;
      }
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
          this.showToast(data.message || 'Đã duyệt bài viết thành công!', 'success');
          this.loadPendingPosts();
          this.loadScheduledPosts();
        } else {
          this.showToast(data.detail || 'Lỗi phê duyệt bài', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi máy chủ khi duyệt: ' + e.message, 'error');
      }
    },
    async rejectPendingPost(post) {
      const reason = prompt('Nhập lý do từ chối bài viết (tùy chọn):');
      if (reason === null) return;
      try {
        const res = await this.authFetch(`/api/posts/${post.id}/reject`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: reason })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.showToast('Đã từ chối bài viết.', 'info');
          this.loadPendingPosts();
        }
      } catch (e) {
        this.showToast('Lỗi máy chủ: ' + e.message, 'error');
      }
    },
    async deleteScheduledPost(id) {
      if (!confirm('Bạn có chắc chắn muốn xóa bài viết này?')) return;
      try {
        const res = await this.authFetch(`/api/posts/${id}`, { method: 'DELETE' });
        if (res.ok) {
          this.showToast('Đã xóa bài viết.', 'info');
          this.loadScheduledPosts();
          this.loadPendingPosts();
        }
      } catch (e) {
        this.showToast('Lỗi khi xóa bài: ' + e.message, 'error');
      }
    },
    async publishNow(id) {
      try {
        const res = await this.authFetch(`/api/posts/${id}/publish-now`, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
          this.showToast('🚀 Đã xuất bản bài viết thành công!', 'success');
          this.loadScheduledPosts();
        } else {
          this.showToast(data.detail || 'Lỗi đăng ngay', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi kết nối: ' + e.message, 'error');
      }
    },

    // ── CALENDAR METHODS ──
    async loadCalendarEvents() {
      try {
        const res = await this.authFetch('/api/calendar/events');
        const data = await res.json();
        this.calendarEvents = data.events || [];
      } catch (e) {
        console.error('Error loading calendar events:', e);
      }
    },

    // ── TEMPLATES & HASHTAGS METHODS ──
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
      } catch (e) {
        console.error('Error loading templates/hashtags:', e);
      }
    },
    insertVariable(varKey) {
      const tag = `{${varKey}}`;
      this.postForm.fb_caption = (this.postForm.fb_caption || '') + ' ' + tag;
      this.postForm.ig_caption = (this.postForm.ig_caption || '') + ' ' + tag;
    },
    applyHashtagGroup() {
      if (!this.selectedHashtagGroupId) return;
      const group = this.hashtagGroups.find(g => g.id === this.selectedHashtagGroupId);
      if (group) {
        this.postForm.fb_caption = (this.postForm.fb_caption || '') + '\n\n' + group.hashtags;
        this.postForm.ig_caption = (this.postForm.ig_caption || '') + '\n\n' + group.hashtags;
        this.showToast(`Đã chèn nhóm hashtag '${group.name}'!`, 'success');
      }
      this.selectedHashtagGroupId = '';
    },
    applyCaptionTemplate() {
      if (!this.selectedCaptionTemplateId) return;
      const tpl = this.captionTemplates.find(t => t.id === this.selectedCaptionTemplateId);
      if (tpl) {
        this.postForm.fb_caption = tpl.content;
        this.postForm.ig_caption = tpl.content;
        this.showToast(`Đã áp dụng mẫu '${tpl.name}'!`, 'success');
      }
      this.selectedCaptionTemplateId = '';
    },

    // ── SETTINGS METHODS ──
    async loadSettings() {
      try {
        const res = await this.authFetch('/api/settings');
        if (res.ok) {
          const data = await res.json();
          this.settingsForm = { ...this.settingsForm, ...data };
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
          this.settingsForm.app_password = '';
          this.settingsForm.admin_password = '';
          this.settingsForm.staff_password = '';
          this.loadSettings();
        } else {
          this.showToast(data.detail || 'Lỗi lưu cài đặt', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi máy chủ khi lưu cài đặt: ' + e.message, 'error');
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
        this.connectionStatus = data;
        if (data.facebook && data.facebook.connected) {
          this.showToast('✅ Kết nối Facebook Page thành công!', 'success');
        } else {
          this.showToast('❌ Kết nối Facebook thất bại: ' + (data.facebook?.error || 'Lỗi Token'), 'error');
        }
      } catch (e) {
        this.showToast('Lỗi kiểm tra kết nối: ' + e.message, 'error');
      } finally {
        this.isTesting = false;
      }
    }
  }
}).mount('#app');
