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

      isSubmitting: false,
      isTesting: false,
      isSaving: false,
      isGeneratingAi: false,
      isGeneratingAiHook: false,

      scheduleEnabled: false,
      dateInput: '',
      timeInput: '',

      postForm: {
        fb_caption: '',
        ig_caption: '',
        google_caption: '',
        images: [],
        target_fb: true,
        target_ig: true,
        target_story: false,
        target_google: false,
        google_action_type: 'LEARN_MORE',
        google_action_url: '',
        story_image: null,
        story_template: 'organic',
        story_hook: '',
        story_link: ''
      },

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
        staff_password: ''
      },

      metaStatus: {
        facebook: { connected: false, page_name: '', page_id: '', picture: '' },
        instagram: { connected: false, username: '', account_id: '', profile_picture: '' }
      },

      metaExchange: {
        app_id: '2039281703363967',
        app_secret: '',
        short_token: ''
      },
      isConvertingToken: false,

      aiModal: {
        show: false,
        isLoading: false,
        userHint: '',
        result: null
      },

      toast: {
        show: false,
        message: '',
        type: 'info'
      },
      errorModal: {
        show: false,
        content: ''
      },

      studioModal: {
        show: false,
        isExporting: false,
        showSafeZone: true,
        activeTemplate: 'organic',
        fabricCanvas: null,
        productImgObj: null,
        safeZoneGroup: null
      },
      studioTemplates: [
        { id: 'organic', name: 'Siêu Thị Hữu Cơ', icon: '🌿' },
        { id: 'juice', name: 'Juice Bar', icon: '🍹' },
        { id: 'sale', name: 'Giờ Vàng Sale', icon: '🔥' },
        { id: 'magazine', name: 'Tạp Chí Ẩm Thực', icon: '✨' },
        { id: 'polaroid', name: 'Chụp Polaroid', icon: '📷' }
      ],

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

      calendarCurrentDate: new Date(),
      calendarEvents: [],
      selectedCalendarPost: null,

      mediaLibrary: [],
      mediaSearch: '',
      selectedMediaTag: 'Tất cả',
      mediaTags: ['Tất cả', 'Trái cây', 'Nước ép', 'Bánh ngọt', 'Chăm sóc', 'Khuyến mãi', 'ROOTS'],
      isLoadingMedia: false,
      selectedMediaFiles: [],
      isBatchDeleting: false,

      hashtagGroups: [],
      captionTemplates: [],
      newHashtagGroup: { name: '', hashtags: '', category: 'Chung' },
      newTemplate: { name: '', content: '', category: 'Sản phẩm', brand_voice: 'Bán hàng' },
      dynamicVariables: [
        { key: '{ten_san_pham}', label: 'Tên sản phẩm', desc: 'Tên sản phẩm tự động' },
        { key: '{gia_ban}', label: 'Giá bán', desc: 'Giá ưu đãi hiện tại' },
        { key: '{gia_goc}', label: 'Giá gốc', desc: 'Giá trước khuyến mãi' },
        { key: '{xuat_xu}', label: 'Xuất xứ', desc: 'Nơi sản xuất hữu cơ' },
        { key: '{link_mua}', label: 'Link mua', desc: 'Đường dẫn roots.vn' },
        { key: '{hotline}', label: 'Hotline', desc: 'Số điện thoại hỗ trợ' },
        { key: '{dia_chi}', label: 'Địa chỉ', desc: 'Địa chỉ cửa hàng ROOTS' }
      ],

      bulkModal: {
        show: false,
        file: null,
        isUploading: false,
        previewData: [],
        step: 1
      },

      activeJob: {
        id: null,
        status: 'idle',
        progress: 0,
        current_step: '',
        error: '',
        timer: null
      },
      showJobModal: false,

      scheduledPosts: [],
      historyPosts: [],
      showToken: false
    };
  },
  computed: {
    calendarMonthYear() {
      const d = this.calendarCurrentDate;
      return `Tháng ${d.getMonth() + 1}, ${d.getFullYear()}`;
    },
    calendarDays() {
      const d = this.calendarCurrentDate;
      const year = d.getFullYear();
      const month = d.getMonth();
      const firstDayOfMonth = new Date(year, month, 1).getDay();
      const daysInMonth = new Date(year, month + 1, 0).getDate();
      const daysInPrevMonth = new Date(year, month, 0).getDate();

      const days = [];
      const startDayOffset = (firstDayOfMonth + 6) % 7;

      for (let i = startDayOffset - 1; i >= 0; i--) {
        days.push({
          date: new Date(year, month - 1, daysInPrevMonth - i),
          isCurrentMonth: false,
          dayNumber: daysInPrevMonth - i
        });
      }

      for (let i = 1; i <= daysInMonth; i++) {
        days.push({
          date: new Date(year, month, i),
          isCurrentMonth: true,
          dayNumber: i
        });
      }

      const remainingDays = 42 - days.length;
      for (let i = 1; i <= remainingDays; i++) {
        days.push({
          date: new Date(year, month + 1, i),
          isCurrentMonth: false,
          dayNumber: i
        });
      }

      return days;
    }
  },
  async mounted() {
    await this.checkAuth();
    if (this.isAuthenticated) {
      this.initApp();
    }
  },
  methods: {
    async checkAuth() {
      try {
        const res = await fetch('/api/auth/check');
        const data = await res.json();
        if (data.authenticated) {
          this.isAuthenticated = true;
          this.currentUserRole = data.role || 'staff';
        } else {
          this.isAuthenticated = false;
        }
      } catch (e) {
        this.isAuthenticated = false;
      }
    },
    async submitLogin() {
      if (!this.loginPassword) return;
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
          this.initApp();
          this.showToast(`Chào mừng bạn quay trở lại (${this.currentUserRole === 'admin' ? '👑 Quản Trị Viên' : '🧑‍💼 Nhân Viên'})!`, 'success');
        } else {
          this.loginError = data.detail || 'Mật khẩu không đúng. Vui lòng thử lại.';
        }
      } catch (err) {
        this.loginError = 'Lỗi kết nối máy chủ.';
      } finally {
        this.isLoggingIn = false;
      }
    },
    async logout() {
      try {
        await fetch('/api/auth/logout', { method: 'POST' });
      } catch (e) {}
      this.isAuthenticated = false;
      this.currentUserRole = 'staff';
    },
    initApp() {
      this.initScheduleDateTime();
      this.loadSettings();
      this.loadScheduledPosts();
      this.loadPendingPosts();
      this.loadHistoryPosts();
      this.loadRootsCategories();
      this.loadRootsData();
      this.loadCalendarEvents();
      this.loadMediaLibrary();
      this.loadTemplatesAndHashtags();
    },
    async authFetch(url, options = {}) {
      const res = await fetch(url, options);
      if (res.status === 401) {
        this.isAuthenticated = false;
        throw new Error('Phiên đăng nhập đã hết hạn.');
      }
      return res;
    },
    initScheduleDateTime() {
      const now = new Date();
      now.setHours(now.getHours() + 1);
      this.dateInput = now.toISOString().split('T')[0];
      const hh = String(now.getHours()).padStart(2, '0');
      const mm = String(now.getMinutes()).padStart(2, '0');
      this.timeInput = `${hh}:${mm}`;
    },
    showToast(message, type = 'info') {
      this.toast.message = message;
      this.toast.type = type;
      this.toast.show = true;
      setTimeout(() => {
        this.toast.show = false;
      }, 3500);
    },
    selectTab(tab) {
      if (tab === 'settings' && this.currentUserRole !== 'admin') {
        this.showToast('Bạn cần quyền Quản trị viên để mở Cài đặt.', 'warning');
        return;
      }
      this.activeTab = tab;
      if (tab === 'queue') {
        this.loadScheduledPosts();
        this.loadPendingPosts();
      } else if (tab === 'history') {
        this.loadHistoryPosts();
      } else if (tab === 'calendar') {
        this.loadCalendarEvents();
      } else if (tab === 'media') {
        this.loadMediaLibrary();
      } else if (tab === 'templates') {
        this.loadTemplatesAndHashtags();
      } else if (tab === 'settings') {
        this.loadSettings();
      }
    },
    async loadPendingPosts() {
      if (this.currentUserRole !== 'admin') return;
      try {
        const res = await this.authFetch('/api/posts?filter_type=pending');
        const data = await res.json();
        if (res.ok) {
          this.pendingPosts = data.posts || [];
        }
      } catch (e) {}
    },
    async approvePost(postId, action = 'publish_now') {
      try {
        const res = await this.authFetch(`/api/posts/${postId}/approve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action })
        });
        const data = await res.json();
        if (res.ok) {
          this.showToast(data.message || '✅ Đã phê duyệt bài viết!', 'success');
          this.loadPendingPosts();
          this.loadScheduledPosts();
          this.loadHistoryPosts();
        } else {
          this.showToast(data.detail || 'Lỗi phê duyệt bài viết', 'error');
        }
      } catch (err) {
        this.showToast(err.message, 'error');
      }
    },
    async rejectPost(postId) {
      const reason = prompt('Nhập lý do từ chối (tùy chọn):', 'Nội dung chưa đạt chuẩn');
      if (reason === null) return;
      try {
        const res = await this.authFetch(`/api/posts/${postId}/reject`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: reason.trim() })
        });
        const data = await res.json();
        if (res.ok) {
          this.showToast('Đã từ chối bài viết', 'info');
          this.loadPendingPosts();
          this.loadHistoryPosts();
        } else {
          this.showToast(data.detail || 'Lỗi từ chối bài viết', 'error');
        }
      } catch (err) {
        this.showToast(err.message, 'error');
      }
    },
    async submitPost() {
      if (this.isSubmitting) return;
      if (!this.postForm.fb_caption && !this.postForm.ig_caption && !this.postForm.google_caption && !this.postForm.story_hook) {
        this.showToast('Vui lòng nhập ít nhất 1 nội dung caption hoặc hook.', 'warning');
        return;
      }
      if (this.postForm.target_ig && this.postForm.images.length === 0) {
        this.showToast('Instagram yêu cầu ít nhất 1 hình ảnh.', 'warning');
        return;
      }

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
          google_action_type: this.postForm.google_action_type || 'LEARN_MORE',
          google_action_url: this.postForm.google_action_url || '',
          story_image: this.postForm.story_image,
          story_template: this.postForm.story_template || 'organic',
          story_hook: this.postForm.story_hook || '',
          story_link: this.postForm.story_link || '',
          action: this.scheduleEnabled ? 'schedule' : 'now'
        };

        if (this.scheduleEnabled) {
          payload.scheduled_time = `${this.dateInput}T${this.timeInput}:00`;
        }

        const res = await this.authFetch('/api/posts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
          if (data.status === 'pending_approval') {
            this.showToast('📤 Bài viết đã gửi vào Hàng Đợi chờ Admin phê duyệt!', 'info');
          } else if (this.scheduleEnabled) {
            this.showToast('⏰ Đã lên lịch bài viết thành công!', 'success');
          } else {
            this.showToast('🚀 Đã xuất bản bài viết thành công!', 'success');
          }
          this.resetPostForm();
          this.loadScheduledPosts();
          this.loadPendingPosts();
          this.loadHistoryPosts();
          this.loadCalendarEvents();
        } else {
          throw new Error(data.detail || 'Lỗi tạo bài viết');
        }
      } catch (err) {
        this.showToast(err.message, 'error');
      } finally {
        this.isSubmitting = false;
      }
    },
    resetPostForm() {
      this.postForm = {
        fb_caption: '',
        ig_caption: '',
        google_caption: '',
        images: [],
        target_fb: true,
        target_ig: true,
        target_story: false,
        target_google: false,
        google_action_type: 'LEARN_MORE',
        google_action_url: '',
        story_image: null,
        story_template: 'organic',
        story_hook: '',
        story_link: ''
      };
      this.scheduleEnabled = false;
      this.initScheduleDateTime();
    },
    async handleFileUpload(event) {
      const files = event.target.files;
      if (!files || files.length === 0) return;
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
        if (res.ok && data.files) {
          data.files.forEach(f => this.postForm.images.push(f));
          this.showToast(`Đã tải lên ${data.files.length} ảnh`, 'success');
        }
      } catch (err) {
        this.showToast('Lỗi tải ảnh lên: ' + err.message, 'error');
      }
    },
    removeImage(idx) {
      this.postForm.images.splice(idx, 1);
      if (this.currentIgPreviewIdx >= this.postForm.images.length) {
        this.currentIgPreviewIdx = Math.max(0, this.postForm.images.length - 1);
      }
    },
    getMediaUrl(filename) {
      if (!filename) return '';
      if (filename.startsWith('http://') || filename.startsWith('https://')) return filename;
      return `/api/media/${filename}`;
    },
    async loadScheduledPosts() {
      try {
        const res = await this.authFetch('/api/posts?filter_type=scheduled');
        const data = await res.json();
        if (res.ok) this.scheduledPosts = data.posts || [];
      } catch (e) {}
    },
    async loadHistoryPosts() {
      try {
        const res = await this.authFetch('/api/posts?filter_type=history');
        const data = await res.json();
        if (res.ok) this.historyPosts = data.posts || [];
      } catch (e) {}
    },
    async loadCalendarEvents() {
      try {
        const res = await this.authFetch('/api/calendar/events');
        const data = await res.json();
        if (res.ok) this.calendarEvents = data.events || [];
      } catch (e) {}
    },
    async loadMediaLibrary() {
      this.isLoadingMedia = true;
      try {
        const res = await this.authFetch(`/api/media/library?search=${encodeURIComponent(this.mediaSearch)}&tag=${encodeURIComponent(this.selectedMediaTag)}`);
        const data = await res.json();
        if (res.ok) this.mediaLibrary = data.items || [];
      } catch (e) {}
      finally {
        this.isLoadingMedia = false;
      }
    },
    async loadTemplatesAndHashtags() {
      try {
        const [hRes, tRes] = await Promise.all([
          this.authFetch('/api/hashtag-groups'),
          this.authFetch('/api/caption-templates')
        ]);
        const hData = await hRes.json();
        const tData = await tRes.json();
        if (hRes.ok) this.hashtagGroups = hData.groups || [];
        if (tRes.ok) this.captionTemplates = tData.templates || [];
      } catch (e) {}
    },
    async generatePostFromProduct(p) {
      if (this.isGeneratingPost) return;
      this.isGeneratingPost = true;
      this.generatingProductId = p.id || p.MaNoiBo;
      try {
        const res = await this.authFetch('/api/roots/1click-post', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(p)
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.postForm.images = data.images || [];
          this.postForm.fb_caption = `🌿 [ROOTS] ${data.product_name}\n\nThương hiệu: ${data.brand}\nGiá ưu đãi: ${this.formatRootsPrice(data.price)}\n\nKhám phá ngay tại roots.vn! #rootsvn #organic`;
          this.postForm.ig_caption = `✨ ${data.product_name} - ${data.brand}\n\nSản phẩm hữu cơ cao cấp chính hãng từ ROOTS.\n\n#roots #healthy #organic #vietnam`;
          this.postForm.google_caption = `Khám phá ngay ${data.product_name} tại ROOTS Organic Store & Juice Bar!`;
          this.selectTab('composer');
          this.showToast('✅ Đã nạp sản phẩm vào bộ soạn bài!', 'success');
        } else {
          throw new Error('Không thể nạp sản phẩm');
        }
      } catch (err) {
        this.showToast(err.message, 'error');
      } finally {
        this.isGeneratingPost = false;
        this.generatingProductId = null;
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
          this.settingsForm.has_admin_password = Boolean(s.has_admin_password);
          this.settingsForm.has_staff_password = Boolean(s.has_staff_password);

          this.settingsForm.fb_page_access_token = '';
          this.settingsForm.imgbb_api_key = '';
          this.settingsForm.gemini_api_key = '';
          this.settingsForm.google_client_secret = '';
          this.settingsForm.app_password = '';
          this.settingsForm.admin_password = '';
          this.settingsForm.staff_password = '';

          this.metaExchange.app_id = '2039281703363967';
          this.testIntegrations();
        }
      } catch (e) {}
    },
    async testIntegrations() {
      this.isTesting = true;
      try {
        const payload = {
          fb_page_id: this.settingsForm.fb_page_id
        };
        if (this.settingsForm.fb_page_access_token && !this.settingsForm.fb_page_access_token.includes('...')) {
          payload.fb_page_access_token = this.settingsForm.fb_page_access_token;
        }
        if (this.settingsForm.ig_business_account_id) {
          payload.ig_business_account_id = this.settingsForm.ig_business_account_id;
        }
        const res = await this.authFetch('/api/settings/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
          if (data.facebook) this.metaStatus.facebook = data.facebook;
          if (data.instagram) this.metaStatus.instagram = data.instagram;
        }
      } catch (e) {}
      finally {
        this.isTesting = false;
      }
    },
    async saveSettings() {
      this.isSaving = true;
      try {
        const payload = {
          fb_page_id: this.settingsForm.fb_page_id,
          ig_business_account_id: this.settingsForm.ig_business_account_id,
          google_client_id: this.settingsForm.google_client_id,
          gemini_model: this.settingsForm.gemini_model,
        };

        if (this.settingsForm.fb_page_access_token && !this.settingsForm.fb_page_access_token.includes('...')) {
          payload.fb_page_access_token = this.settingsForm.fb_page_access_token.trim();
        }
        if (this.settingsForm.imgbb_api_key && !this.settingsForm.imgbb_api_key.includes('...')) {
          payload.imgbb_api_key = this.settingsForm.imgbb_api_key.trim();
        }
        if (this.settingsForm.gemini_api_key && !this.settingsForm.gemini_api_key.includes('...')) {
          payload.gemini_api_key = this.settingsForm.gemini_api_key.trim();
        }
        if (this.settingsForm.google_client_secret && !this.settingsForm.google_client_secret.includes('...')) {
          payload.google_client_secret = this.settingsForm.google_client_secret.trim();
        }
        if (this.settingsForm.admin_password && this.settingsForm.admin_password.trim()) {
          payload.admin_password = this.settingsForm.admin_password.trim();
        }
        if (this.settingsForm.staff_password && this.settingsForm.staff_password.trim()) {
          payload.staff_password = this.settingsForm.staff_password.trim();
        }
        if (this.settingsForm.app_password && this.settingsForm.app_password.trim()) {
          payload.app_password = this.settingsForm.app_password.trim();
        }

        const res = await this.authFetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.showToast('✅ Đã lưu cài đặt an toàn thành công!', 'success');
          this.loadSettings();
        } else {
          throw new Error(data.detail || 'Lỗi lưu cài đặt');
        }
      } catch (err) {
        this.showToast(err.message, 'error');
      } finally {
        this.isSaving = false;
      }
    },
    async loadRootsCategories() {
      try {
        const res = await this.authFetch('/api/roots/categories');
        const data = await res.json();
        if (res.ok && data.categories) {
          this.rootsCategories = data.categories;
        }
      } catch (e) {}
    },
    async loadRootsData() {
      this.isLoadingRoots = true;
      try {
        let endpoint = `/api/roots/products?page=${this.rootsPagination.current_page}&page_size=20`;
        if (this.rootsSearchQuery) {
          endpoint += `&search=${encodeURIComponent(this.rootsSearchQuery)}`;
        }
        if (this.selectedRootsCategory && this.selectedRootsCategory !== 'all') {
          endpoint += `&category=${encodeURIComponent(this.selectedRootsCategory)}`;
        }
        if (this.isFlashSaleOnly) {
          endpoint = `/api/roots/flash-sale?page=${this.rootsPagination.current_page}&page_size=20`;
        }

        const res = await this.authFetch(endpoint);
        const data = await res.json();
        if (res.ok && (data.status === 'success' || Array.isArray(data.data))) {
          this.rootsProducts = data.data || [];
          if (data.pagination) {
            this.rootsPagination = data.pagination;
          }
        }
      } catch (err) {
        console.error('Error loading roots data:', err);
      } finally {
        this.isLoadingRoots = false;
      }
    },
    selectRootsCategory(cat) {
      this.selectedRootsCategory = cat;
      this.rootsPagination.current_page = 1;
      this.loadRootsData();
    },
    loadRootsProducts(p) {
      if (typeof p === 'number' && p >= 1) {
        this.changeRootsPage(p);
      } else {
        this.loadRootsData();
      }
    },
    changeRootsPage(p) {
      if (p < 1) p = 1;
      this.rootsPagination.current_page = p;
      this.loadRootsData();
      const el = document.querySelector('#app');
      if (el) window.scrollTo({ top: 0, behavior: 'smooth' });
    },
    resetRootsFilters() {
      this.selectedRootsCategory = 'all';
      this.rootsSearchQuery = '';
      this.isFlashSaleOnly = false;
      this.rootsPagination.current_page = 1;
      this.loadRootsData();
    },
    getRootsImageUrl(img) {
      if (!img) return 'https://roots.vn/themes/roots/assets/images/no-image.png';
      if (img.startsWith('http://') || img.startsWith('https://')) return img;
      return `https://img.roots.vn/products/${img.split('?')[0]}`;
    },
    getRootsProductUrl(p) {
      if (!p) return 'https://roots.vn';
      if (p.Slug) {
        if (p.DanhMucSlug) return `https://roots.vn/danh-muc/${p.DanhMucSlug}/${p.Slug}`;
        return `https://roots.vn/danh-muc/${p.Slug}`;
      }
      return 'https://roots.vn';
    },
    formatRootsPrice(val) {
      const num = parseFloat(val || 0);
      if (num <= 0) return 'Liên hệ';
      return num.toLocaleString('vi-VN') + 'đ';
    },
    hasDiscount(p) {
      const gKm = parseFloat(p.GiaSauKm || 0);
      const gOld = parseFloat(p.GiaTruocKm || 0);
      return gOld > gKm && gKm > 0;
    },
    calcDiscountPercent(p) {
      const gKm = parseFloat(p.GiaSauKm || 0);
      const gOld = parseFloat(p.GiaTruocKm || 0);
      if (gOld <= gKm || gOld <= 0) return 0;
      return Math.round(((gOld - gKm) / gOld) * 100);
    },
    toggleSelectComboProduct(p) {
      const id = p.id || p.MaNoiBo;
      const idx = this.selectedComboProducts.findIndex(x => (x.id || x.MaNoiBo) === id);
      if (idx >= 0) {
        this.selectedComboProducts.splice(idx, 1);
      } else {
        this.selectedComboProducts.push(p);
      }
    },
    isComboProductSelected(p) {
      const id = p.id || p.MaNoiBo;
      return this.selectedComboProducts.some(x => (x.id || x.MaNoiBo) === id);
    },
    getFbName() {
      return this.metaStatus.facebook.page_name || 'ROOTS - Organic Store & Juice Bar';
    },
    getFbPic() {
      return this.metaStatus.facebook.picture || this.metaStatus.instagram.profile_picture || '';
    },
    getIgName() {
      return this.metaStatus.instagram.username || 'rootsvn.official';
    },
    getIgPic() {
      return this.metaStatus.instagram.profile_picture || this.metaStatus.facebook.picture || '';
    },
    getBrandName() {
      return this.metaStatus.facebook.page_name || (this.metaStatus.instagram.username ? '@' + this.metaStatus.instagram.username : 'ROOTS - Organic Store & Juice Bar');
    },
    getBrandPic() {
      return this.metaStatus.facebook.picture || this.metaStatus.instagram.profile_picture || '';
    },
    formatDateTime(dateStr) {
      if (!dateStr) return '';
      const d = new Date(dateStr);
      return d.toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric' });
    },
    deletePostItem(id) {
      if (!confirm('Bạn có chắc muốn xóa bài viết này?')) return;
      this.authFetch(`/api/posts/${id}`, { method: 'DELETE' }).then(res => {
        if (res.ok) {
          this.showToast('Đã xóa bài viết', 'info');
          this.loadScheduledPosts();
          this.loadPendingPosts();
          this.loadHistoryPosts();
        }
      });
    },
    publishNow(id) {
      this.authFetch(`/api/posts/${id}/publish-now`, { method: 'POST' }).then(res => res.json()).then(data => {
        this.showToast(data.message || 'Đang tiến hành đăng bài...', 'info');
        this.loadScheduledPosts();
        this.loadPendingPosts();
        this.loadHistoryPosts();
      });
    },
    showErrorModal(err) {
      this.errorModal.content = err;
      this.errorModal.show = true;
    },
    truncate(str, max = 50) {
      if (!str) return '';
      return str.length > max ? str.slice(0, max) + '...' : str;
    }
  }
}).mount('#app');
