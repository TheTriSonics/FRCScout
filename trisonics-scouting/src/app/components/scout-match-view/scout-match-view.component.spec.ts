import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ScoutMatchViewComponent } from './scout-match-view.component';

describe('ScoutMatchViewComponent', () => {
  let component: ScoutMatchViewComponent;
  let fixture: ComponentFixture<ScoutMatchViewComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ ScoutMatchViewComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(ScoutMatchViewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
